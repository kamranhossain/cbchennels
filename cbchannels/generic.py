from channels import Group
from channels.sessions import channel_session, http_session
from channels.auth import channel_session_user_from_http, channel_session_user
from .base import apply_decorator, consumer


class GroupMixin(object):
    """
    Add reply_channel to the Group at connect and broadcast at receive

    Usage:

    class MyGroupConsumers(GroupConsumers):
        path = '(?P<id>\d+)'
        group_name = 'test_{id}'
    """
    group_name = None

    def get_group_name(self, **kwargs):
        return (self.group_name or self.channel_name).format(**kwargs)

    def get_group(self):
        return Group(self.get_group_name(**self.kwargs), alias=self._channel_alias, channel_layer=self._channel_layer)

    def broadcast(self, content):
        self.get_group().send(content)

    def on_connect(self, message, **kwargs):
        super(GroupMixin, self).on_connect(message, **kwargs)
        self.get_group().add(self.reply_channel)

    def on_disconnect(self, message, **kwargs):
        super(GroupMixin, self).on_disconnect(message, **kwargs)
        self.get_group().discard(self.reply_channel)

    def on_receive(self, message, **kwargs):
        super(GroupMixin, self).on_receive(message, **kwargs)
        self.broadcast(message.content)


class SessionMixin(object):
    """
    Add access to the user sessions (http and channels)
    """

    @classmethod
    def get_decorators(cls):
        decorators = super(SessionMixin, cls).get_decorators()
        decorators.append(http_session)
        if channel_session_user not in decorators:
            decorators.append(channel_session)
        return decorators

    @property
    def session(self):
        return self.message.session

    @property
    def http_session(self):
        return self.message.http_session


class UserMixin(object):

    @classmethod
    def get_decorators(cls):
        decorators = super(UserMixin, cls).get_decorators()
        decorators.append(channel_session_user)
        if channel_session in decorators:
            decorators.remove(channel_session)  # channel_session_user already include channel_session decorator
        return decorators

    @apply_decorator(channel_session_user_from_http)
    def on_connect(self, *args, **kwargs):
        return super(UserMixin, self).on_connect(*args, **kwargs)

    @property
    def user(self):
        return self.message.user


class PermissionMixin(object):
    permissions = []

    def __check_permission(self):
        for perm in self.permissions:
            if not perm(self):
                return False
        return True

    def on_receive(self, *args, **kwargs):
        if self.__check_permission():
            super(PermissionMixin, self).on_receive(*args, **kwargs)


class RoomMixin(SessionMixin):
    channel_name = '_room'

    @consumer(command="^join$", room=r'(?P<room>\w+)')
    def join(self, message, room):
        self.session['rooms'].add(room)

    @consumer(command="^leave$", room=r'(?P<room>\w+)')
    def leave(self, message, room):
        self.session['rooms'].remove(room)

    @consumer(command="^send$", room=r'(?P<room>\w+)')
    def send(self, message, room):
        if room in self.session:
            self.get_room_group(room).send(self.message['message'])

    def get_room_group(self, room):
        return Group(room, alias=self._channel_alias, channel_layer=self._channel_layer)


