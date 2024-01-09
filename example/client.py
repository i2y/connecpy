from conpy.context import ClientContext
from conpy.exceptions import ConPyServerException

import haberdasher_conpy, haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


def main():
    client = haberdasher_conpy.HaberdasherClient(server_url, timeout=timeout_s)

    try:
        response = client.MakeHat(
            ctx=ClientContext(),
            request=haberdasher_pb2.Size(inches=12),
        )
        if not response.HasField("name"):
            print("We didn't get a name!")
        print(response)
    except ConPyServerException as e:
        print(e.code, e.message, e.to_dict())


if __name__ == "__main__":
    main()
