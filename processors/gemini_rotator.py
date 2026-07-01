import time
import logging
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)


class GeminiRotator:

    def __init__(self):
        self.keys = [k for k in settings.GEMINI_KEYS if k]
        self.current_index = 0
        self.total_keys = len(self.keys)

        if self.total_keys == 0:
            raise ValueError("No Gemini API keys configured")

        logger.info(f"GeminiRotator initialized with {self.total_keys} keys")

    def _get_current_key(self):
        return self.keys[self.current_index]

    def _rotate(self):
        self.current_index = (self.current_index + 1) % self.total_keys
        logger.debug(f"Rotated to key index {self.current_index}")

    def _say_hi(self, key):
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            response = model.generate_content(
                "Hi",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=5
                ),
            )
            return response.text is not None
        except Exception as e:
            logger.warning(f"Say hi failed for key {key[:10]}...: {e}")
            return False

    def call(self, prompt, use_heavy=False):
        model_name = (
            settings.GEMINI_MODEL_HEAVY if use_heavy else settings.GEMINI_MODEL
        )

        for attempt in range(self.total_keys):
            key = self._get_current_key()

            if not self._say_hi(key):
                logger.info(
                    f"Key {key[:10]}... dead, rotating (attempt {attempt + 1})"
                )
                self._rotate()
                continue

            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)

                generation_config = genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                )

                response = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                result = response.text
                logger.debug(
                    f"Gemini call success with key {key[:10]}... "
                    f"(attempt {attempt + 1})"
                )
                return result

            except Exception as e:
                logger.warning(
                    f"Gemini call failed with key {key[:10]}...: {e} "
                    f"(attempt {attempt + 1})"
                )
                self._rotate()
                time.sleep(2)

        raise RuntimeError("All 7 Gemini keys failed")
