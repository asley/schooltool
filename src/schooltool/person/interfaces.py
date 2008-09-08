#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005 Shuttleworth Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Person interfaces

$Id$
"""
import calendar
import pytz

import zope.interface
import zope.schema

import zope.app.container.constraints
from zope.app import container
from zope.annotation.interfaces import IAnnotatable, IAttributeAnnotatable
from zope.location.interfaces import ILocation

from schooltool.common import SchoolToolMessage as _
from schooltool.group.interfaces import IGroupMember


def vocabulary(choices):
    """Create a SimpleVocabulary from a list of values and titles.

    >>> v = vocabulary([('value1', u"Title for value1"),
    ...                 ('value2', u"Title for value2")])
    >>> for term in v:
    ...   print term.value, '|', term.token, '|', term.title
    value1 | value1 | Title for value1
    value2 | value2 | Title for value2

    """
    return zope.schema.vocabulary.SimpleVocabulary(
        [zope.schema.vocabulary.SimpleTerm(v, title=t) for v, t in choices])


class IPasswordWriter(zope.interface.Interface):
    """Interface for setting a password for a person."""

    def setPassword(password):
        """Set the password of the person."""


class IHavePreferences(IAnnotatable):
    """An object that can have preferences. Namely a Person."""


class IReadPerson(IGroupMember):
    """Publically accessible part of IPerson."""

    title = zope.schema.TextLine(
        title=_("Full name"),
        description=_("Name that should be displayed"))

    photo = zope.schema.Bytes(
        title=_("Photo"),
        required=False,
        description=_("""Photo (in JPEG format)"""))

    username = zope.schema.TextLine(
        title=_("Username"))

    # XXX: Should not be here. At most this could be in an adapter.
    overlaid_calendars = zope.interface.Attribute(
        """Additional calendars to overlay.

            A user may select a number of calendars that should be displayed in
            the calendar view, in addition to the user's calendar.

            This is a relationship property.""") # XXX Please use a Field.

    def checkPassword(password):
        """Check if the provided password is the same as the one set
        earlier using setPassword.

        Returns True if the passwords match.
        """

    def hasPassword():
        """Check if the user has a password.

        You can remove user's password (effectively disabling the account) by
        passing None to setPassword.  You can reenable the account by passing
        a new password to setPassword.
        """

    def __eq__(other):
        """Compare two persons."""


class IWritePerson(zope.interface.Interface):
    """Protected part of IPerson."""

    def setPassword(password):
        """Set the password in a hashed form, so it can be verified later.

        Setting password to None disables the user account.
        """


class IPerson(IReadPerson, IWritePerson, IAttributeAnnotatable):
    """Person.

    A person has a number of informative fields such as name, an optional
    photo, and so on.

    A person can also be a user of the system, therefore IPerson defines
    `username`, and methods for setting/checking passwords (`setPassword`,
    `checkPassword` and `hasPassword`).

    Use IPersonContained instead if you want a person in context (that is,
    one that you can use to traverse to other persons/groups/resources).
    """


class IPersonFactory(zope.interface.Interface):

    def __call__(*args, **kw):
        """Create a new Person instance."""

    def createManagerUser(username, system_name):
        """Create a person that will be the manager user.

        As different persons have different required fields and
        schooltool has to create the user automatically each person
        factory should have person specific manager user.
        """

    def columns():
        """Return a list of default columns for person lists."""

    def sortOn():
        """Return the default sort order for persons."""


class IPersonContainer(container.interfaces.IContainer):
    """Container of persons."""

    container.constraints.contains(IPerson)

    super_user = zope.interface.Attribute(
        """Absolute administrator for this schooltool instance.

           A user that no matter which groups he is in or is not in has the
           administrative privileges.""")


class IPersonContained(IPerson, container.interfaces.IContained):
    """Person contained in an IPersonContainer."""

    container.constraints.containers(IPersonContainer)


class ICalendarDisplayPreferences(zope.interface.Interface):
    """Preferences for displaying calendar events."""

    timezone = zope.schema.Choice(
        title=_("Time Zone"),
        description=_("Time Zone used to display your calendar"),
        values=pytz.common_timezones)

    timeformat = zope.schema.Choice(
        title=_("Time Format"),
        description=_("Time Format"),
        vocabulary=vocabulary([("%H:%M", _("HH:MM")),
                               ("%I:%M %p", _("HH:MM am/pm"))]))

    dateformat = zope.schema.Choice(
        title=_("Date Format"),
        description=_("Date Format"),
        vocabulary=vocabulary([("%m/%d/%y", _("MM/DD/YY")),
                               ("%Y-%m-%d", _("YYYY-MM-DD")),
                               ("%d %B, %Y", _("Day Month, Year"))]))

    # SUNDAY and MONDAY are integers, 6 and 0 respectivley
    weekstart = zope.schema.Choice(
        title=_("Week starts on:"),
        description=_("Start display of weeks on Sunday or Monday"),
        vocabulary=vocabulary([(calendar.SATURDAY, _("Saturday")),
                               (calendar.SUNDAY, _("Sunday")),
                               (calendar.MONDAY, _("Monday"))]))


class IPersonPreferences(ICalendarDisplayPreferences):
    """Preferences stored in an annotation on a person."""

    __parent__ = zope.interface.Attribute(
        """Person who owns these preferences""")

    # XXX: Only available in SchoolTool, but that's ok for now.
    cal_periods = zope.schema.Bool(
        title=_("Show periods"),
        description=_("Show period names in daily view"))

    cal_public = zope.schema.Bool(
        title=_("Make calendar public"),
        description=_("Make calendar public"))
