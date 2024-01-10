import asyncio

import httpx

from connecpy.context import ClientContext
from connecpy.exceptions import ConnecpyServerException

import haberdasher_connecpy, haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


async def main():
    session = httpx.AsyncClient(
        base_url=server_url,
        timeout=timeout_s,
    )
    client = haberdasher_connecpy.AsyncHaberdasherClient(server_url, session=session)

    try:
        response = await client.MakeHat(
            ctx=ClientContext(),
            request=haberdasher_pb2.Size(inches=12),
            # Optionally provide a session per request
            # session=session,
        )
        if not response.HasField("name"):
            print("We didn't get a name!")
        print(response)
    except ConnecpyServerException as e:
        print(e.code, e.message, e.to_dict())
    finally:
        # Close the session (could also use a context manager)
        await session.aclose()


if __name__ == "__main__":
    asyncio.run(main())
