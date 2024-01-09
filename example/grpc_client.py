import asyncio
from typing import cast

from grpc.aio import insecure_channel

import haberdasher_pb2


target = "localhost:50051"


async def main():
    channel = insecure_channel(target)
    make_hat = channel.unary_unary(
        "/i2y.conpy.example.Haberdasher/MakeHat",
        request_serializer=haberdasher_pb2.Size.SerializeToString,
        response_deserializer=haberdasher_pb2.Hat.FromString,
    )
    request = haberdasher_pb2.Size(inches=12)
    response = cast(haberdasher_pb2.Hat, await make_hat(request))
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
