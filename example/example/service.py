import random

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.server import ServiceContext

from .haberdasher_connecpy import Haberdasher
from .haberdasher_pb2 import Hat, Size


class HaberdasherService(Haberdasher):
    async def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
        print("remaining_time: ", ctx.timeout_ms())
        if req.inches <= 0:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT, "inches I can't make a hat that small!"
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
