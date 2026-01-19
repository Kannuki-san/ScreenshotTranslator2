import threading
import queue
import logging
import subprocess
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    sd = None
    HAS_SOUNDDEVICE = False

import numpy as np
from kokoro import KPipeline
from .config import get_settings

logger = logging.getLogger(__name__)

class KokoroTTS:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(KokoroTTS, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        logger.info("Initializing Kokoro TTS...")
        try:
            # lang_code='j' for Japanese as per user request
            self.pipeline = KPipeline(lang_code='j', repo_id='hexgrad/Kokoro-82M')
            self.sample_rate = 24000
            self._queue = queue.Queue()
            self._current_gen_id = 0
            self._stop_event = threading.Event()
            self._is_generating = False  # Track busy state
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            logger.info("Kokoro TTS initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro TTS: {e}")
            self.pipeline = None
        
        self._initialized = True

    def is_busy(self) -> bool:
        """Check if TTS is currently generating or playing audio."""
        return self._is_generating or not self._queue.empty()

    def _worker_loop(self):
        while True:
            try:
                # Wait for a play request
                item = self._queue.get()
                if item is None:
                    break
                
                self._is_generating = True
                text, gen_id = item
                if gen_id != self._current_gen_id:
                    self._queue.task_done()
                    self._is_generating = False
                    continue

                if not self.pipeline:
                     self._queue.task_done()
                     self._is_generating = False
                     continue

                logger.info(f"Starting TTS for gen_id={gen_id}: {text[:30]}...")
                
                # Determine playback method
                use_aplay = not HAS_SOUNDDEVICE

                # Generate audio
                try:
                    generator = self.pipeline(
                        text, 
                        voice='af_heart', 
                        speed=1, 
                        split_pattern=r'[、。！？\n]+' # Explicitly split by JP punctuation
                    )
                    
                    aplay_proc = None
                    if use_aplay:
                        # Start aplay process
                        # Kokoro 24khz, mono?
                        aplay_proc = subprocess.Popen(
                            ['aplay', '-f', 'S16_LE', '-r', '24000', '-c', '1', '-q'],
                            stdin=subprocess.PIPE
                        )

                    for i, (gs, ps, audio) in enumerate(generator):
                        if gen_id != self._current_gen_id:
                            logger.info(f"TTS interrupted for gen_id={gen_id}")
                            break
                        
                        # Ensure audio is numpy array (might be torch tensor)
                        if hasattr(audio, 'numpy'):
                            audio = audio.numpy()
                        if hasattr(audio, 'cpu'): # Should be on CPU for numpy
                             pass 
                        
                        logger.info(f"Generated audio chunk {i}: shape={audio.shape}, dtype={audio.dtype}")

                        if use_aplay and aplay_proc:
                             # Convert float32 to int16
                             # Clip to avoid overflow just in case
                             audio_clipped = np.clip(audio, -1.0, 1.0)
                             audio_int16 = (audio_clipped * 32767).astype(np.int16)
                             try:
                                 aplay_proc.stdin.write(audio_int16.tobytes())
                                 aplay_proc.stdin.flush()
                                 logger.info(f"Wrote chunk {i} to aplay ({len(audio_int16)} samples)")
                             except BrokenPipeError:
                                 logger.error("aplay check: BrokenPipe")
                                 break
                        elif HAS_SOUNDDEVICE:
                            # Use sounddevice
                            logger.info(f"Playing chunk {i} via sounddevice")
                            sd.play(audio, self.sample_rate)
                            sd.wait()
                            logger.info(f"Finished playing chunk {i}")

                    logger.info("TTS generator finished. Closing aplay if active.")
                    if aplay_proc:
                        aplay_proc.stdin.close()
                        aplay_proc.wait()
                        logger.info("aplay process finished.")

                except Exception as e:
                    logger.error(f"TTS generation error: {e}")
                    if use_aplay and aplay_proc:
                        try:
                            aplay_proc.kill()
                        except:
                            pass
                
                self._queue.task_done()
                self._is_generating = False
                
            except Exception as e:
                logger.error(f"TTS worker error: {e}")
                self._is_generating = False

    def speak(self, text: str, interrupt: bool = True):
        if not text or not self.pipeline:
            return

        if interrupt:
            # Increment generation ID to invalidate pending/current tasks
            self._current_gen_id += 1
            # Stop any currently playing audio immediately
            if HAS_SOUNDDEVICE:
                try:
                    sd.stop()
                except Exception:
                    pass
        
        self._queue.put((text, self._current_gen_id))

# Global instance
tts_engine = KokoroTTS()
