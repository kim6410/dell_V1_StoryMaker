from __future__ import annotations

import asyncio

from nemotron_lab.backend.schemas import LabRequest
from nemotron_lab.backend.service import service


async def main() -> int:
    request = LabRequest(
        mode="chat",
        prompt="한글로 정확히 OK 한 단어만 답하세요.",
        model="deepseek-ai/deepseek-v4-flash",
        source_language="자동 감지",
        target_language="한국어",
        temperature=0.0,
        max_tokens=64,
        stream=False,
    )
    result = await service.execute(
        request=request,
        user_id=0,
        username="internal_probe",
        client_ip="127.0.0.1",
    )
    print(f"STATUS={result.get('status')}")
    print(f"OK={result.get('ok')}")
    print(f"TOKENS={result.get('total_tokens', 0)}")
    print(f"LATENCY_MS={result.get('latency_ms', 0)}")
    text = str(result.get('content') or result.get('error') or '').replace("\n", " ")[:180]
    print(f"OUTPUT={text}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
