import asyncio

from grpc.aio import server

import haberdasher_pb2_grpc
from service import HaberdasherService


host = "localhost:50051"


async def main():
    s = server()
    haberdasher_pb2_grpc.add_HaberdasherServicer_to_server(HaberdasherService(), s)
    bound_port = s.add_insecure_port(host)
    print(f"localhost:{bound_port}")
    await s.start()
    await s.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(main())
