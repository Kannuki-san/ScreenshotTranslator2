import threading
import queue
import logging
import subprocess
import os
import re
import tempfile
try:
    import soundfile as sf
except ImportError:
    sf = None
import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    sd = None
    HAS_SOUNDDEVICE = False

try:
    from misaki import ja
    HAS_MISAKI = True
except ImportError:
    HAS_MISAKI = False

from kokoro_onnx import Kokoro
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
        
        logger.info("Initializing Kokoro TTS (ONNX)...")
        self.kokoro = None
        self.g2p = None
        
        # Check for model files
        model_path = "kokoro-v1.0.onnx"
        voices_path = "voices-v1.0.bin"
        
        if os.path.exists(model_path) and os.path.exists(voices_path):
            try:
                self.kokoro = Kokoro(model_path, voices_path)
                logger.info("Kokoro ONNX loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Kokoro ONNX: {e}")
        else:
            logger.warning(f"Kokoro model files not found: {model_path}, {voices_path}")
            logger.warning("Please download them to the project root.")

        if HAS_MISAKI:
            try:
                self.g2p = ja.JAG2P()
                logger.info("Misaki G2P loaded.")
            except Exception as e:
                logger.error(f"Failed to load Misaki G2P: {e}")
        else:
            logger.warning("Misaki not found. Install 'misaki' for better Japanese support.")

        self.sample_rate = 24000
        self._queue = queue.Queue()
        self._current_gen_id = 0
        self._stop_event = threading.Event()
        self._is_generating = False
        
        # Buffer for the "Next" text to speak immediately after current finishes
        self._next_text = None
        self._next_text_lock = threading.Lock()

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        
        self._initialized = True

    def is_busy(self) -> bool:
        """Check if TTS is currently generating or playing audio."""
        return self._is_generating or not self._queue.empty()

    def set_next_text(self, text: str):
        with self._next_text_lock:
            self._next_text = text
            logger.info(f"Buffered next text (len={len(text)}): {text[:20]}...")

    def _split_text(self, text, limit=150):
        """Split text into smaller chunks significantly below the limit to prevent hangs."""
        if len(text) <= limit:
            return [text]
        
        chunks = []
        current_chunk = ""
        # Split by common delimiters
        parts = re.split(r'([。、\n？！?!])', text)
        
        for part in parts:
            if not part: 
                continue
            if len(current_chunk) + len(part) > limit:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = part
            else:
                current_chunk += part
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _worker_loop(self):
        logger.info("TTS Worker thread started.")
        while True:
            try:
                item = self._queue.get()
                if item is None:
                    break
                
                self._is_generating = True
                full_text, gen_id = item
                
                try:
                    # Check cancellation before starting
                    if gen_id != self._current_gen_id:
                        self._queue.task_done()
                        self._is_generating = False
                        continue

                    if not self.kokoro:
                         logger.error("Kokoro engine not loaded. Cannot speak.")
                         continue

                    # Split long text into chunks
                    chunks = self._split_text(full_text)
                    if len(chunks) > 1:
                        logger.info(f"Text too long, split into {len(chunks)} chunks.")

                    for i, text in enumerate(chunks):
                        # Re-check interruption between chunks
                        if gen_id != self._current_gen_id:
                            logger.info(f"TTS interrupted for gen_id={gen_id} during chunk {i}")
                            break

                        # G2P Pre-processing
                        input_text = text
                        is_phonemes = False
                        if self.g2p:
                            try:
                                phonemes, _ = self.g2p(text)
                                input_text = phonemes
                                is_phonemes = True
                            except Exception as e:
                                logger.error(f"G2P error: {e}, using raw text")
                        
                        use_aplay = not HAS_SOUNDDEVICE
                        aplay_proc = None

                        try:
                            stream = self.kokoro.create_stream(
                                input_text, 
                                voice='af_heart', 
                                speed=1.0, 
                                lang='j',
                                is_phonemes=is_phonemes
                            )

                            if use_aplay:
                                aplay_proc = subprocess.Popen(
                                    ['aplay', '-f', 'S16_LE', '-r', '24000', '-c', '1', '-q'],
                                    stdin=subprocess.PIPE
                                )

                            async def play_stream():
                                 count = 0
                                 async for samples, sample_rate in stream:
                                    if gen_id != self._current_gen_id:
                                        break
                                    
                                    if use_aplay and aplay_proc:
                                        audio_clipped = np.clip(samples, -1.0, 1.0)
                                        audio_int16 = (audio_clipped * 32767).astype(np.int16)
                                        try:
                                            aplay_proc.stdin.write(audio_int16.tobytes())
                                            aplay_proc.stdin.flush()
                                        except (BrokenPipeError, OSError):
                                            break
                                    elif HAS_SOUNDDEVICE:
                                        sd.play(samples, sample_rate)
                                        sd.wait()
                                    
                                    count += 1

                            import asyncio
                            asyncio.run(play_stream())

                            if aplay_proc:
                                aplay_proc.stdin.close()
                                aplay_proc.wait()

                        except Exception as e:
                            logger.error(f"Chunk generation error: {e}")
                            if use_aplay and aplay_proc:
                                try: aplay_proc.kill() 
                                except: pass
                
                finally:
                    self._queue.task_done()
                    self._is_generating = False

                    # Check for buffered next text regardless of success/failure
                    next_text_to_speak = None
                    with self._next_text_lock:
                        if self._next_text:
                            logger.info("Found buffered text, grabbing it.")
                            next_text_to_speak = self._next_text
                            self._next_text = None
                    
                    if next_text_to_speak:
                        logger.info("Queuing buffered text immediately.")
                        self.speak(next_text_to_speak, interrupt=False)

            except Exception as e:
                logger.error(f"TTS worker error: {e}")
                self._is_generating = False

    def speak(self, text: str, interrupt: bool = True):
        if not text:
            return
        
        # Clear any pending buffered text if we are speaking explicitly
        with self._next_text_lock:
            self._next_text = None

        if interrupt:
            self._current_gen_id += 1
            if HAS_SOUNDDEVICE:
                try:
                    sd.stop()
                except Exception:
                    pass
        
        self._queue.put((text, self._current_gen_id))

# Global instance
tts_engine = KokoroTTS()
