from tortoise import Tortoise
from tortoise.models import Model
from tortoise.fields import (
    IntField,
    BigIntField,
    CharField,
    TextField,
    DatetimeField,
    BooleanField,
    ForeignKeyField,
    ForeignKeyRelation,
    ReverseRelation,
)


class Guild(Model):
    id = BigIntField(pk=True)
    prefix = CharField(max_length=32)
    moderator_role = BigIntField(null=True)
    mute_role = BigIntField(null=True)
    mutes: ReverseRelation["Mute"]
    warns: ReverseRelation["Warn"]

    class Meta:
        table = "guilds"


class User(Model):
    id = BigIntField(pk=True)
    exp = IntField(default=0)
    level = IntField(default=0)
    balance = IntField(default=0)
    daily_streak = DatetimeField(null=True)
    last_daily = DatetimeField(null=True)
    mutes: ReverseRelation["Mute"]
    warns: ReverseRelation["Warn"]

    class Meta:
        table = "users"

    def __str__(self):
        return (
            f"<User id:{self.id} exp:{self.exp} "
            f"level:{self.level} bal:{self.balance}>"
        )


class Mute(Model):
    id = IntField(pk=True)
    moderator = IntField()
    reason = TextField(null=True)
    start = DatetimeField(auto_now_add=True)
    end = DatetimeField()
    active = BooleanField(default=True)
    user: ForeignKeyRelation[User] = ForeignKeyField(
        "models.User", related_name="mutes"
    )
    guild: ForeignKeyRelation[Guild] = ForeignKeyField(
        "models.Guild", related_name="mutes"
    )

    class Meta:
        table = "mutes"


class Warn(Model):
    id = IntField(pk=True)
    moderator = IntField()
    reason = TextField(null=True)
    when = DatetimeField(auto_now_add=True)
    user: ForeignKeyRelation[User] = ForeignKeyField(
        "models.User", related_name="warns"
    )
    guild: ForeignKeyRelation[Guild] = ForeignKeyField(
        "models.Guild", related_name="warns"
    )

    class Meta:
        table = "warns"


async def init_database():
    # logging.info("Initializing database connection...")
    await Tortoise.init(
        db_url="mysql://nagatoro:nagatoro@localhost/nagatoro",
        modules={"models": [__name__]},
    )
    await Tortoise.generate_schemas()
    # logging.info("Successfully connected to database")