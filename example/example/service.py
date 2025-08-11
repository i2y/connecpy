import random
from typing import AsyncIterator

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.request import RequestContext

from .haberdasher_connecpy import Haberdasher
from .haberdasher_pb2 import Hat, Size


class HaberdasherService(Haberdasher):
    async def MakeHat(self, req: Size, ctx: RequestContext) -> Hat:
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

    async def MakeSimilarHats(
        self, req: Size, ctx: ServiceContext
    ) -> AsyncIterator[Hat]:
        """Server Streaming RPC: Returns multiple hats of similar size"""
        if req.inches <= 0:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT, "inches: I can't make a hat that small!"
            )

        # Generate 3 similar hats with different colors
        colors = ["white", "black", "brown", "red", "blue"]
        hat_types = ["bowler", "baseball cap", "top hat", "derby", "fedora"]

        for i in range(3):
            hat = Hat(
                size=req.inches + random.randint(-1, 1),  # Slight size variation
                color=colors[i % len(colors)],
            )
            if req.description:  # Use description if provided
                hat.name = f"{req.description} #{i + 1}"
            else:
                hat.name = hat_types[i % len(hat_types)]

            yield hat
