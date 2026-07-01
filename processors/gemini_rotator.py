"""
GeminiRotator - Xoay vòng API key Gemini free tier
- Không dùng say_hi() (lãng phí quota)
- Xoay key khi gặp 429 / ResourceExhausted
- Backoff tăng dần, retry thông minh
"""
import time
import logging
import re

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from config import settings

logger = logging.getLogger(__name__)


class GeminiRotator:

    def __init__(self):
        self.keys = list(settings.GEMINI_KEYS)
        if not self.keys:
            raise ValueError("Không có GEMINI_KEY nào được cấu hình")

        self.current_index = 0
        self.total_keys = len(self.keys)
        # Theo dõi thời điểm mỗi key bị rate-limit
        self._cooldown_until: dict[int, float] = {}

        logger.info(f"GeminiRotator: {self.total_keys} keys sẵn sàng")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_available_key(self):
        """Trả về (index, key) của key chưa bị cooldown. None nếu tất cả đang chờ."""
        now = time.time()
        for offset in range(self.total_keys):
            idx = (self.current_index + offset) % self.total_keys
            if now >= self._cooldown_until.get(idx, 0):
                self.current_index = (idx + 1) % self.total_keys
                return idx, self.keys[idx]
        return None, None

    def _set_cooldown(self, idx: int, seconds: float = 65.0):
        self._cooldown_until[idx] = time.time() + seconds
        logger.warning(f"Key[{idx}] cooldown {seconds:.0f}s")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, prompt: str, max_output_tokens: int = 2048) -> str:
        """
        Gọi Gemini với xoay vòng key. Tự động retry khi rate-limit.
        Raise RuntimeError khi tất cả key đều kiệt.
        """
        attempts = 0
        max_attempts = self.total_keys * 3  # tối đa 3 vòng xoay

        while attempts < max_attempts:
            idx, key = self._next_available_key()

            if key is None:
                # Tất cả key đang cooldown — chờ key sớm nhất hết hạn
                earliest = min(self._cooldown_until.values())
                wait = max(0, earliest - time.time()) + 2
                logger.info(f"Tất cả key đang cooldown, chờ {wait:.0f}s...")
                time.sleep(wait)
                attempts += 1
                continue

            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(settings.GEMINI_MODEL)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=max_output_tokens,
                    ),
                )
                text = response.text
                if not text:
                    raise ValueError("Gemini trả về response rỗng")

                # Delay礼貌 sau mỗi call thành công
                time.sleep(settings.DELAY_BETWEEN_CALLS_SEC)
                return text

            except (ResourceExhausted, Exception) as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "resource" in err_str or "exhausted" in err_str:
                    logger.warning(f"Key[{idx}] rate-limit: {e}")
                    self._set_cooldown(idx, 65.0)
                elif "invalid" in err_str or "api_key" in err_str or "forbidden" in err_str:
                    logger.error(f"Key[{idx}] không hợp lệ — loại khỏi pool")
                    self._set_cooldown(idx, 86400.0)  # 24h
                else:
                    logger.warning(f"Key[{idx}] lỗi: {e} — thử key tiếp theo")
                    self._set_cooldown(idx, 10.0)

                attempts += 1
                time.sleep(2)
                continue

        raise RuntimeError(
            f"Tất cả {self.total_keys} Gemini key đều thất bại sau {max_attempts} lần thử"
        )
