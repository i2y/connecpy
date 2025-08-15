import random
from collections.abc import AsyncIterator

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.request import RequestContext

from .haberdasher_connecpy import Haberdasher
from .haberdasher_pb2 import Hat, Size


class HaberdasherService(Haberdasher):
    async def make_hat(self, request: Size, ctx: RequestContext) -> Hat:
        print("remaining_time: ", ctx.timeout_ms())
        if request.inches <= 0:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT, "inches I can't make a hat that small!"
            )
        response = Hat(
            size=request.inches,
            color=random.choice(["white", "black", "brown", "red", "blue"]),
        )
        if random.random() > 0.5:
            response.name = random.choice(
                ["bowler", "baseball cap", "top hat", "derby"]
            )

        return response

    async def make_similar_hats(
        self, request: Size, ctx: RequestContext
    ) -> AsyncIterator[Hat]:
        """Server Streaming RPC: Returns multiple hats of similar size"""
        if request.inches <= 0:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT, "inches: I can't make a hat that small!"
            )

        # Generate 3 similar hats with different colors
        colors = ["white", "black", "brown", "red", "blue"]
        hat_types = ["bowler", "baseball cap", "top hat", "derby", "fedora"]

        for i in range(3):
            hat = Hat(
                size=request.inches + random.randint(-1, 1),  # Slight size variation
                color=colors[i % len(colors)],
            )
            if request.description:  # Use description if provided
                hat.name = f"{request.description} #{i + 1}"
            else:
                hat.name = hat_types[i % len(hat_types)]

            yield hat
