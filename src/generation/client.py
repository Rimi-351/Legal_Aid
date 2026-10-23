"""
src/generation/client.py
------------------------
Ollama local generation API client with deterministic parameters,
timeout control, and resource/latency measurement on CPU.
"""

import os
import time
import json
import psutil
from typing import Dict, Any, Optional
import urllib.request
import urllib.error

from .prompts import LEGAL_SYSTEM_PROMPT


class OllamaGenerationClient:
    """
    HTTP client for local Ollama server running quantized instruct models on CPU.
    """

    def __init__(
        self,
        model_name: str = "qwen2.5:3b",
        base_url: str = "http://127.0.0.1:11434",
        timeout_sec: float = 90.0,
        temperature: float = 0.1,
        max_tokens: int = 350,
        context_window: int = 2048,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = context_window

    def is_server_alive(self) -> bool:
        """Verifies if the Ollama server is responsive."""
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_ollama_process_rss_mb(self) -> float:
        """Finds running Ollama process and returns its resident memory (RSS) in MB."""
        total_rss = 0.0
        try:
            for proc in psutil.process_iter(["name", "memory_info"]):
                if proc.info["name"] and "ollama" in proc.info["name"].lower():
                    total_rss += proc.info["memory_info"].rss / (1024 * 1024)
        except Exception:
            pass
        return round(total_rss, 2)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submits prompt to Ollama generate endpoint and returns detailed performance metrics.
        """
        if system_prompt is None:
            system_prompt = LEGAL_SYSTEM_PROMPT

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.context_window,
                "seed": 42,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        initial_rss = self.get_ollama_process_rss_mb()
        t0 = time.perf_counter()

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                total_latency = round(time.perf_counter() - t0, 3)
                post_rss = self.get_ollama_process_rss_mb()
                result_json = json.loads(response.read().decode("utf-8"))

                eval_count = result_json.get("eval_count", 0)
                eval_duration_ns = result_json.get("eval_duration", 0)
                eval_duration_sec = (
                    round(eval_duration_ns / 1e9, 3) if eval_duration_ns else 0.0
                )
                tokens_per_sec = (
                    round(eval_count / eval_duration_sec, 2)
                    if eval_duration_sec > 0
                    else 0.0
                )

                return {
                    "answer": result_json.get("response", "").strip(),
                    "total_latency_s": total_latency,
                    "eval_count": eval_count,
                    "eval_duration_s": eval_duration_sec,
                    "tokens_per_sec": tokens_per_sec,
                    "process_rss_mb": post_rss,
                    "error": None,
                }

        except urllib.error.HTTPError as e:
            return {
                "answer": "",
                "total_latency_s": round(time.perf_counter() - t0, 3),
                "eval_count": 0,
                "eval_duration_s": 0.0,
                "tokens_per_sec": 0.0,
                "process_rss_mb": self.get_ollama_process_rss_mb(),
                "error": f"HTTPError {e.code}: {e.reason}",
            }
        except urllib.error.URLError as e:
            return {
                "answer": "",
                "total_latency_s": round(time.perf_counter() - t0, 3),
                "eval_count": 0,
                "eval_duration_s": 0.0,
                "tokens_per_sec": 0.0,
                "process_rss_mb": self.get_ollama_process_rss_mb(),
                "error": f"URLError: {e.reason}",
            }
        except TimeoutError:
            return {
                "answer": "",
                "total_latency_s": round(time.perf_counter() - t0, 3),
                "eval_count": 0,
                "eval_duration_s": 0.0,
                "tokens_per_sec": 0.0,
                "process_rss_mb": self.get_ollama_process_rss_mb(),
                "error": f"Timeout after {self.timeout_sec} seconds",
            }
        except Exception as e:
            return {
                "answer": "",
                "total_latency_s": round(time.perf_counter() - t0, 3),
                "eval_count": 0,
                "eval_duration_s": 0.0,
                "tokens_per_sec": 0.0,
                "process_rss_mb": self.get_ollama_process_rss_mb(),
                "error": str(e),
            }
