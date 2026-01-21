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
        self._current_text = None
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

    def _split_by_language(self, text):
        """
        Split text into chunks of English (contiguous ASCII characters) and others (Japanese/Mainly non-ASCII).
        Returns list of (text_chunk, is_english_bool).
        """
        if not text:
            return []
            
        # Split by contiguous ASCII characters (Hex 20-7E)
        # This includes alphanumerics, symbols, and spaces.
        parts = re.split(r'([\x20-\x7E]+)', text)
        chunks = []
        for p in parts:
            if not p:
                continue
            # Check if this part is purely ASCII
            is_en = bool(re.match(r'^[\x20-\x7E]+$', p))
            chunks.append((p, is_en))
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
                self._current_text = full_text
                
                try:
                    # Check cancellation before starting
                    if gen_id != self._current_gen_id:
                        self._queue.task_done()
                        self._is_generating = False
                        continue

                    if not self.kokoro:
                         logger.error("Kokoro engine not loaded. Cannot speak.")
                         continue

                    # Split text by language
                    chunks = self._split_by_language(full_text)
                    audio_segments = []
                    
                    # Generate audio for all chunks first
                    for i, (text, is_en) in enumerate(chunks):
                        if gen_id != self._current_gen_id:
                            logger.info(f"TTS interrupted for gen_id={gen_id}")
                            audio_segments = None
                            break
                        
                        try:
                            # Selection of language and G2P
                            speed = 1.0
                            if is_en:
                                lang = 'en-us' # Use correct English code
                                input_text = text
                                is_phonemes = False
                                speed = 1.0
                                # Kokoro internal tokenizer uses espeak-ng (via espeakng_loader)
                            else:
                                lang = 'j'
                                input_text = text
                                is_phonemes = False
                                speed = 1.25 # Japanese 25% faster
                                if self.g2p:
                                    try:
                                        phonemes, _ = self.g2p(text)
                                        input_text = phonemes
                                        is_phonemes = True
                                    except Exception as e:
                                        logger.error(f"G2P error: {e}, using raw text")

                            # Generate audio stream (we collect all samples)
                            stream = self.kokoro.create_stream(
                                input_text, 
                                voice='af_heart', 
                                speed=speed, 
                                lang=lang,
                                is_phonemes=is_phonemes
                            )
                            
                            chunk_samples = []
                            async def consume_stream():
                                async for samples, _ in stream:
                                    chunk_samples.append(samples)
                            
                            import asyncio
                            asyncio.run(consume_stream())
                            
                            if chunk_samples:
                                audio_segments.extend(chunk_samples)

                        except Exception as e:
                            logger.error(f"Chunk generation error: {e}")
                    
                    # Play combined audio if not interrupted
                    if audio_segments and gen_id == self._current_gen_id:
                        full_audio = np.concatenate(audio_segments)
                        
                        if HAS_SOUNDDEVICE:
                            sd.play(full_audio, 24000)
                            sd.wait()
                        else:
                            # Fallback to aplay (write all at once)
                            try:
                                aplay_proc = subprocess.Popen(
                                    ['aplay', '-f', 'S16_LE', '-r', '24000', '-c', '1', '-q'],
                                    stdin=subprocess.PIPE
                                )
                                audio_clipped = np.clip(full_audio, -1.0, 1.0)
                                audio_int16 = (audio_clipped * 32767).astype(np.int16)
                                aplay_proc.stdin.write(audio_int16.tobytes())
                                aplay_proc.stdin.close()
                                aplay_proc.wait()
                            except Exception as e:
                                logger.error(f"Aplay error: {e}")

                finally:
                    self._queue.task_done()
                    self._is_generating = False
                    self._current_text = None  # Clear current text

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
                self._current_text = None

    def is_content_active(self, text: str) -> bool:
        """Check if text is currently being spoken or is buffered as next."""
        if not text:
            return False
        
        # Check buffer
        with self._next_text_lock:
            if self._next_text == text:
                return True
        
        # Check current (approximate, no lock needed for simple string check)
        if self._current_text == text:
            return True
            
        return False

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
