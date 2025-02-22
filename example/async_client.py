import asyncio

import httpx

from connecpy.context import ClientContext
from connecpy.exceptions import ConnecpyServerException

import haberdasher_connecpy
import haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


async def main():
    async with httpx.AsyncClient(
        base_url=server_url,
        timeout=timeout_s,
    ) as session:
        client = haberdasher_connecpy.AsyncHaberdasherClient(
            server_url, session=session
        )

        # Example 1: POST request with Zstandard compression
        try:
            response = await client.MakeHat(
                ctx=ClientContext(),
                request=haberdasher_pb2.Size(inches=12),
                headers={
                    "Content-Encoding": "zstd",  # Request compression
                    "Accept-Encoding": "br",  # Response compression
                },
            )
            print("POST with Zstandard compression:", response)
        except ConnecpyServerException as e:
            print(e.code, e.message, e.to_dict())

        # Example 2: GET request with Brotli compression
        try:
            response = await client.MakeHat(
                ctx=ClientContext(
                    headers={
                        "Accept-Encoding": "zstd",  # Response compression
                    }
                ),
                request=haberdasher_pb2.Size(inches=8),
                use_get=True,  # Enable GET request
            )
            print("\nGET with Brotli compression:", response)
        except ConnecpyServerException as e:
            print(e.code, e.message, e.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
