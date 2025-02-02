import random

from connecpy.exceptions import InvalidArgument
from connecpy.context import ServiceContext

from haberdasher_pb2 import Hat, Size


class HaberdasherService(object):
    def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
        print("remaining_time: ", ctx.time_remaining())
        if req.inches <= 0:
            raise InvalidArgument(
                argument="inches", error="I can't make a hat that small!"
            )
        response = Hat(
            size=req.inches,
            color=random.choice(["white", "black", "brown", "red", "blue"]),
        )
        if random.random() > 0.5:
            response.name = random.choice(
                ["bowler", "baseball cap", "top hat", "derby"]
            )

        return response
