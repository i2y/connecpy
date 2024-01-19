import asyncio

from grpc.aio import insecure_channel

import haberdasher_pb2
import haberdasher_pb2_grpc


target = "localhost:50051"


async def main():
    channel = insecure_channel(target)
    stub = haberdasher_pb2_grpc.HaberdasherStub(channel)
    request = haberdasher_pb2.Size(inches=12)
    response = await stub.MakeHat(request)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
