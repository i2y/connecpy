import asyncio

import httpx

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
        async with haberdasher_connecpy.AsyncHaberdasherClient(
            server_url,
            session=session,
            send_compression="zstd",
            accept_compression=("br",),
        ) as client:
            # Example 1: POST request with Zstandard compression, receiving Brotli compressed response
            try:
                response = await client.MakeHat(
                    request=haberdasher_pb2.Size(inches=12),
                    headers={
                        "Content-Encoding": "zstd",  # Request compression
                    },
                )
                print("POST with Zstandard and Brotli compression:", response)
            except ConnecpyServerException as e:
                print(e.code, e.message, e.to_dict())

        async with haberdasher_connecpy.AsyncHaberdasherClient(
            server_url,
            session=session,
            accept_compression=["zstd"],
        ) as client:
            # Example 2: GET request, receiving Zstandard compressed response
            try:
                response = await client.MakeHat(
                    request=haberdasher_pb2.Size(inches=8),
                    use_get=True,  # Enable GET request
                )
                print("\nGET with Zstandard compression:", response)
            except ConnecpyServerException as e:
                print(e.code, e.message, e.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
