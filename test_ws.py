import argparse
import asyncio
import json
import os

import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect to the Maison Bleue Kids websocket for manual testing."
    )
    parser.add_argument(
        "--token",
        default=os.getenv("MBJ_WS_TOKEN"),
        help="JWT access token. Defaults to the MBJ_WS_TOKEN environment variable.",
    )
    parser.add_argument(
        "--child-id",
        type=int,
        default=int(os.getenv("MBJ_WS_CHILD_ID", "3")),
        help="Child id to connect to. Defaults to MBJ_WS_CHILD_ID or 3.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MBJ_WS_HOST", "localhost:8000"),
        help="Backend host. Defaults to MBJ_WS_HOST or localhost:8000.",
    )
    return parser.parse_args()


async def run_websocket_probe(token: str, child_id: int, host: str) -> None:
    url = f"ws://{host}/ws/{child_id}?token={token}"

    print(f"Connecting to ws://{host}/ws/{child_id}")

    async with websockets.connect(url) as ws:
        print("Connected.\n")

        msg = await ws.recv()
        data = json.loads(msg)
        print(f"{data['type']} - {data['data']['message']}")

        await ws.send(json.dumps({"type": "ping"}))
        await ws.recv()
        print("pong received.\n")

        print("=" * 50)
        print("Listening. Press Ctrl+C to stop.")
        print("=" * 50)
        print("In another terminal, you can trigger an event with:")
        print(f"curl -X POST http://{host}/emotions/record \\")
        print('  -H "Content-Type: application/json" \\')
        print('  -H "Authorization: Bearer $MBJ_WS_TOKEN" \\')
        print(f"  -d '{{\"child_id\": {child_id}, \"emotion_id\": 1, \"context\": \"test\"}}'")
        print("=" * 50 + "\n")

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                print("\nEvent received.")
                print(f"   Type : {data.get('type')}")
                print(
                    f"   Data : {json.dumps(data.get('data'), indent=6, ensure_ascii=False)}"
                )
                print(f"   Time : {data.get('timestamp')}\n")
            except websockets.ConnectionClosed:
                print("Connection closed.")
                break
            except KeyboardInterrupt:
                print("\nStopping test.")
                break


if __name__ == "__main__":
    args = parse_args()
    if not args.token:
        raise SystemExit(
            "Missing token. Pass --token or set the MBJ_WS_TOKEN environment variable."
        )

    try:
        asyncio.run(run_websocket_probe(args.token, args.child_id, args.host))
    except KeyboardInterrupt:
        print("\nTest stopped.")
