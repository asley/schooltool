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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
group views.
"""
import zc.table.table
import zc.table.column
from zope.app.dependable.interfaces import IDependable
from zope.cachedescriptors.property import Lazy
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.intid.interfaces import IIntIds
from zope.traversing.browser.interfaces import IAbsoluteURL
from zope.interface import implements, directlyProvides
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.publisher.browser import BrowserView
from zope.component import adapts
from zope.component import getUtility
from zope.component import getMultiAdapter
from zope.security.checker import canAccess
from zope.i18n.interfaces.locales import ICollator
from zope.viewlet.viewlet import ViewletBase
from zope.container.interfaces import INameChooser
from zope.security import checkPermission
from zope.security.proxy import removeSecurityProxy
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.i18n import translate
from z3c.form import field, button, form
from z3c.form.interfaces import HIDDEN_MODE
from zc.table.interfaces import ISortableColumn
from zope.security.interfaces import Unauthorized

from schooltool.app.browser.app import ActiveSchoolYearContentMixin
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.skin.containers import TableContainerView
from schooltool.app.browser.app import BaseAddView, BaseEditView
from schooltool.app.browser.app import ContentTitle
from schooltool.app.browser.states import EditTemporalRelationships
from schooltool.app.browser.states import TemporalRelationshipAddTableMixin
from schooltool.app.browser.states import TemporalRelationshipRemoveTableMixin
from schooltool.app.browser.app import RelationshipViewBase
from schooltool.person.interfaces import IPerson
from schooltool.person.interfaces import IPersonFactory
from schooltool.person.browser.person import PersonTableFilter
from schooltool.basicperson.browser.person import StatusPersonListTable
from schooltool.basicperson.browser.person import EditPersonTemporalRelationships
from schooltool.basicperson.browser.person import BasicPersonTable
from schooltool.course.interfaces import ISection
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.group.group import Group
from schooltool.group.interfaces import IGroup
from schooltool.group.interfaces import IGroupMember
from schooltool.group.interfaces import IGroupContainer, IGroupContained
from schooltool.skin.flourish.viewlet import Viewlet
from schooltool.common.inlinept import InheritTemplate
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.skin import flourish
from schooltool import table

from schooltool.common import SchoolToolMessage as _
from schooltool.basicperson.browser.person import FlourishPersonIDCardsViewBase
from schooltool.report.report import OldReportTask
from schooltool.report.browser.report import RequestRemoteReportDialog


class GroupContainerAbsoluteURLAdapter(BrowserView):

    adapts(IGroupContainer, IBrowserRequest)
    implements(IAbsoluteURL)

    def __str__(self):
        container_id = int(self.context.__name__)
        int_ids = getUtility(IIntIds)
        container = int_ids.getObject(container_id)
        url = str(getMultiAdapter((container, self.request), name='absolute_url'))
        return url + '/groups'

    __call__ = __str__


class GroupContainerView(TableContainerView):
    """A Group Container view."""

    __used_for__ = IGroupContainer

    index_title = _("Group index")


class GroupListView(RelationshipViewBase):
    """View for managing groups that a person or a resource belongs to."""

    __used_for__ = IGroupMember

    @property
    def title(self):
        return _("Groups of ${person}", mapping={'person': self.context.title})
    current_title = _("Current Groups")
    available_title = _("Available Groups")

    def getSelectedItems(self):
        """Return a list of groups the current user is a member of."""
        return [group for group in self.context.groups
                if not ISection.providedBy(group)]

    def getAvailableItemsContainer(self):
        app = ISchoolToolApplication(None)
        groups = IGroupContainer(app, {})
        return groups

    def getCollection(self):
        return self.context.groups


class GroupView(BrowserView):
    """A Group info view."""

    __used_for__ = IGroupContained

    def renderPersonTable(self):
        persons = ISchoolToolApplication(None)['persons']
        formatter = getMultiAdapter((persons, self.request),
                                    table.interfaces.ITableFormatter)
        formatter.setUp(table_formatter=zc.table.table.StandaloneFullFormatter,
                        items=self.getPersons(),
                        batch_size=0)
        return formatter.render()

    def getPersons(self):
        return [member for member in self.context.members
                if canAccess(member, 'title')]

    @property
    def canModify(self):
        return canAccess(self.context.__parent__, '__delitem__')


class MemberViewPersons(RelationshipViewBase):
    """View class for adding / removing members to / from a group."""

    __used_for__ = IGroupContained

    @property
    def title(self):
        return _("Members of ${group}", mapping={'group': self.context.title})
    current_title = _("Current Members")
    available_title = _("Add Members")

    def getSelectedItems(self):
        """Return a list of current group memebers."""
        return filter(IPerson.providedBy, self.context.members)

    def getAvailableItemsContainer(self):
        return ISchoolToolApplication(None)['persons']

    def getCollection(self):
        return self.context.members


class GroupAddView(BaseAddView):
    """A view for adding a group."""


class GroupEditView(BaseEditView):
    """A view for editing group info."""

    __used_for__ = IGroupContained


class GroupsViewlet(ViewletBase):
    """A viewlet showing the groups a person is in."""

    def update(self):
        self.collator = ICollator(self.request.locale)
        groups = [
            group for group in self.context.groups
            if (canAccess(group, 'title') and
                not ISection.providedBy(group))]

        schoolyears_data = {}
        for group in groups:
            sy = ISchoolYear(group.__parent__)
            if sy not in schoolyears_data:
                schoolyears_data[sy] = []
            schoolyears_data[sy].append(group)

        self.schoolyears = []
        for sy in sorted(schoolyears_data, key=lambda x:x.first, reverse=True):
            sy_info = {'obj': sy,
                       'groups': sorted(schoolyears_data[sy],
                                        cmp=self.collator.cmp,
                                        key=lambda x:x.title)}
            self.schoolyears.append(sy_info)

    @property
    def canModify(self):
        return canAccess(self.context.__parent__, '__delitem__')


class FlourishGroupsViewlet(Viewlet):
    """A flourish viewlet showing the groups a person is in."""

    template = ViewPageTemplateFile('templates/f_groupsviewlet.pt')
    render = lambda self, *a, **kw: self.template(*a, **kw)

    def update(self):
        self.collator = ICollator(self.request.locale)
        groups = [
            group for group in self.context.groups
            if (canAccess(group, 'title') and
                not ISection.providedBy(group))]

        schoolyears_data = {}
        for group in groups:
            sy = ISchoolYear(group.__parent__)
            if sy not in schoolyears_data:
                schoolyears_data[sy] = []
            schoolyears_data[sy].append(group)

        self.schoolyears = []
        for sy in sorted(schoolyears_data, key=lambda x:x.first, reverse=True):
            sy_info = {'obj': sy,
                       'groups': sorted(schoolyears_data[sy],
                                        cmp=self.collator.cmp,
                                        key=lambda x:x.title)}
            self.schoolyears.append(sy_info)

    @property
    def canModify(self):
        return canAccess(self.context.__parent__, '__delitem__')


class FlourishGroupFilterWidget(table.table.FilterWidget):

    template = ViewPageTemplateFile('templates/f_group_filter.pt')


class SchoolYearColumn(zc.table.column.GetterColumn):

    def getter(self, item, formatter):
        schoolyear = ISchoolYear(item.__parent__)
        return schoolyear.title

    def getSortKey(self, item, formatter):
        schoolyear = ISchoolYear(item.__parent__)
        return schoolyear.first


class FlourishGroupTableFormatter(table.table.SchoolToolTableFormatter):

    def columns(self):
        title = table.column.LocaleAwareGetterColumn(
            name='title',
            title=_(u"Title"),
            getter=lambda i, f: i.title,
            subsort=True)
        directlyProvides(title, ISortableColumn)
        return [title]

    def makeFormatter(self):
        formatter = table.table.SchoolToolTableFormatter.makeFormatter(self)
        formatter.cssClasses['table'] = 'groups-table relationships-table'
        return formatter


class FlourishGroupListView(EditTemporalRelationships):

    app_states_name = "group-membership"
    dialog_title_template = _("Assign to ${target}")

    current_title = _('Current groups')
    available_title = _('Available groups')

    @Lazy
    def schoolyears(self):
        app = ISchoolToolApplication(None)
        schoolyears = ISchoolYearContainer(app)
        active_schoolyear = schoolyears.getActiveSchoolYear()
        return [schoolyear for schoolyear in schoolyears.values()
                if schoolyear.first >= active_schoolyear.first]

    def getSelectedItems(self):
        groups = EditTemporalRelationships.getSelectedItems(self)
        return [group for group in groups
                if not ISection.providedBy(group) and
                ISchoolYear(group.__parent__) in self.schoolyears]

    def getAvailableItemsContainer(self):
        app = ISchoolToolApplication(None)
        groups = IGroupContainer(app, {})
        return groups

    def getAvailableItems(self):
        result = []
        selected_items = set(self.getSelectedItems())
        for schoolyear in self.schoolyears:
            groups = IGroupContainer(schoolyear)
            result.extend([group for group in groups.values()
                           if group not in selected_items])
        return result

    def getCollection(self):
        return self.context.groups

    def getColumnsAfter(self, prefix):
        columns = super(FlourishGroupListView, self).getColumnsAfter(prefix)
        schoolyear = SchoolYearColumn(
            name='schoolyear',
            title=_(u'School Year'),
            subsort=True)
        directlyProvides(schoolyear, ISortableColumn)
        return [schoolyear] + columns

    def sortOn(self):
        return (('schoolyear', True), ("title", False))

    def setUpTables(self):
        self.available_table = self.createTableFormatter(
            ommit=self.getOmmitedItems(),
            items=self.getAvailableItems(),
            sort_on=self.sortOn(),
            prefix="add_item")
        self.selected_table = self.createTableFormatter(
            filter=lambda l: l,
            items=self.getSelectedItems(),
            sort_on=self.sortOn(),
            prefix="remove_item",
            batch_size=0)

    def getKey(self, item):
        schoolyear = ISchoolYear(item.__parent__)
        return "%s.%s" % (schoolyear.__name__, item.__name__)

    def getTargets(self, keys):
        if not keys:
            return []
        result = []
        sy_groups = {}
        app = ISchoolToolApplication(None)
        schoolyears = ISchoolYearContainer(app)
        for key in keys:
            for sy_name, schoolyear in schoolyears.items():
                if not key.startswith(sy_name+'.'):
                    continue
                if sy_name not in sy_groups:
                    sy_groups[sy_name] = IGroupContainer(schoolyear)
                group = sy_groups[sy_name].get(key[len(sy_name)+1:])
                if group is not None:
                    result.append(group)
        return result


class GroupsTertiaryNavigationManager(flourish.page.TertiaryNavigationManager,
                                      ActiveSchoolYearContentMixin):

    template = InlineViewPageTemplate("""
        <ul tal:attributes="class view/list_class">
          <li tal:repeat="item view/items"
              tal:attributes="class item/class"
              tal:content="structure item/viewlet">
          </li>
        </ul>
    """)

    @property
    def items(self):
        result = []
        active = self.schoolyear
        schoolyears = active.__parent__ if active is not None else {}
        for schoolyear in schoolyears.values():
            url = '%s/%s?schoolyear_id=%s' % (
                absoluteURL(self.context, self.request),
                'groups',
                schoolyear.__name__)
            result.append({
                    'class': schoolyear.first == active.first and 'active' or None,
                    'viewlet': u'<a href="%s">%s</a>' % (url, schoolyear.title),
                    })
        return result


class GroupsAddLinks(flourish.page.RefineLinksViewlet):
    """Manager for Add links in GroupsView"""


class GroupImportLinks(flourish.page.RefineLinksViewlet):
    """Manager for group import links."""


class GroupLinks(flourish.page.RefineLinksViewlet):
    """Manager for public links in GroupView"""

    @property
    def title(self):
        return self.context.title


class GroupAddLinks(flourish.page.RefineLinksViewlet):
    """Manager for Add links in GroupView"""

    def render(self):
        # This check is necessary because the user can be a leader
        # of the context group, which gives him schooltool.edit on it
        if canAccess(self.context.__parent__, '__delitem__'):
            return super(GroupAddLinks, self).render()


class GroupManageActionsLinks(flourish.page.RefineLinksViewlet):
    """Manager for Action links in GroupView"""

    body_template = InlineViewPageTemplate("""
        <ul tal:attributes="class view/list_class">
          <li tal:repeat="item view/renderable_items"
              tal:attributes="class item/class"
              tal:content="structure item/viewlet">
          </li>
        </ul>
    """)

    # We don't want this manager rendered at all
    # if there are no renderable viewlets
    @property
    def renderable_items(self):
        result = []
        for item in self.items:
            render_result = item['viewlet']()
            if render_result and render_result.strip():
                result.append({
                        'class': item['class'],
                        'viewlet': render_result,
                        })
        return result

    def render(self):
        # This check is necessary because the user can be a leader
        # of the context group, which gives him schooltool.edit on it
        if canAccess(self.context.__parent__, '__delitem__'):
            if self.renderable_items:
                return super(GroupManageActionsLinks, self).render()


class GroupDeleteLink(flourish.page.ModalFormLinkViewlet):

    @property
    def dialog_title(self):
        title = _(u'Delete ${group}',
                  mapping={'group': self.context.title})
        return translate(title, context=self.request)

    def render(self, *args, **kw):
        unwrapped = removeSecurityProxy(self.context)
        dependable = IDependable(unwrapped, None)
        if dependable is None or not bool(dependable.dependents()):
            return super(GroupDeleteLink, self).render(*args, **kw)


class GroupAddLinkViewlet(flourish.page.LinkViewlet,
                          ActiveSchoolYearContentMixin):

    @property
    def url(self):
        groups = IGroupContainer(self.schoolyear)
        return '%s/%s' % (absoluteURL(groups, self.request),
                          'addSchoolToolGroup.html')

class GroupAddLinkFromGroupViewlet(GroupAddLinkViewlet):

    @property
    def schoolyear(self):
        return ISchoolYear(self.context.__parent__)

    @property
    def url(self):
        groups = IGroupContainer(self.schoolyear)
        return '%s/%s?camefrom=%s' % (
            absoluteURL(groups, self.request),
            'addSchoolToolGroup.html',
            absoluteURL(self.context, self.request))


class GroupContainerTitle(ContentTitle):

    @property
    def title(self):
        schoolyear = ISchoolYear(self.context)
        return _('Groups for ${schoolyear}',
                 mapping={'schoolyear': schoolyear.title})


class FlourishGroupsView(flourish.page.Page,
                         ActiveSchoolYearContentMixin):

    content_template = InlineViewPageTemplate('''
      <div tal:content="structure context/schooltool:content/ajax/view/container/table" />
    ''')

    @property
    def title(self):
        schoolyear = self.schoolyear
        return _('Groups for ${schoolyear}',
                 mapping={'schoolyear': schoolyear.title})

    @Lazy
    def container(self):
        schoolyear = self.schoolyear
        return IGroupContainer(schoolyear)

    def __call__(self, *args, **kw):
        if not flourish.canView(self.container):
            raise Unauthorized("No permission to view groups.")
        return flourish.page.Page.__call__(self, *args, **kw)


class GroupsTable(table.ajax.Table):

    def columns(self):
        default = table.ajax.Table.columns(self)
        description = zc.table.column.GetterColumn(
            name='description',
            title=_('Description'),
            getter=lambda i, f: i.description or '',
            )
        return default + [description]


class GroupsTableFilter(table.ajax.TableFilter):

    title = _("Group title")


class GroupsTableSchoolYear(flourish.viewlet.Viewlet):

    template = InlineViewPageTemplate('''
      <input type="hidden" name="schoolyear_id"
             tal:define="schoolyear_id view/view/schoolyear/__name__|nothing"
             tal:condition="schoolyear_id"
             tal:attributes="value schoolyear_id" />
    ''')


class GroupsWithSYTable(GroupsTable):

    def columns(self):
        default = table.ajax.Table.columns(self)
        schoolyear = SchoolYearColumn(
            name='schoolyear',
            title=_(u'School Year'),
            subsort=True)
        directlyProvides(schoolyear, ISortableColumn)
        return default + [schoolyear]

    def sortOn(self):
        return (('schoolyear', True), ("title", False))


class GroupListAddRelationshipTable(TemporalRelationshipAddTableMixin,
                                    GroupsWithSYTable):

    def updateFormatter(self):
        ommit = self.view.getOmmitedItems()
        available = self.view.getAvailableItems()
        columns = self.columns()
        self.setUp(formatters=[table.table.url_cell_formatter],
                   columns=columns,
                   ommit=ommit,
                   items=available,
                   table_formatter=self.table_formatter,
                   batch_size=self.batch_size,
                   prefix=self.__name__,
                   css_classes={'table': 'data relationships-table'})


class GroupListRemoveRelationshipTable(TemporalRelationshipRemoveTableMixin,
                                       GroupsWithSYTable):
    pass


class FlourishGroupContainerDeleteView(flourish.containers.ContainerDeleteView):

    def nextURL(self):
        if 'CONFIRM' in self.request:
            schoolyear = ISchoolYear(self.context)
            url = '%s/%s?schoolyear_id=%s' % (
                absoluteURL(ISchoolToolApplication(None), self.request),
                'groups',
                schoolyear.__name__)
            return url
        return flourish.containers.ContainerDeleteView.nextURL(self)


class FlourishGroupView(flourish.form.DisplayForm, ActiveSchoolYearContentMixin):

    template = InheritTemplate(flourish.page.Page.template)
    content_template = ViewPageTemplateFile('templates/f_group_view.pt')
    fields = field.Fields(IGroup)
    fields = fields.select('title', 'description')

    @property
    def canModify(self):
        return checkPermission('schooltool.edit', self.context)

    @property
    def schoolyear(self):
        return ISchoolYear(self.context.__parent__)

    @property
    def title(self):
        return _('Groups for ${schoolyear}',
                 mapping={'schoolyear': self.schoolyear.title})

    @property
    def subtitle(self):
        return self.context.title

    def done_link(self):
        url = self.request.get('done_link', None)
        if url is not None:
            return url
        app = ISchoolToolApplication(None)
        return self.url_with_schoolyear_id(app, view_name='groups')

    def updateWidgets(self):
        super(FlourishGroupView, self).updateWidgets()
        for widget in self.widgets.values():
            if not widget.value:
                widget.mode = HIDDEN_MODE

    def has_members(self):
        return bool(self.context.members)

    def has_leaders(self):
        return bool(self.context.leaders)


class FlourishGroupAddView(flourish.form.AddForm, ActiveSchoolYearContentMixin):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Group Information')
    fields = field.Fields(IGroup)
    fields = fields.select('title', 'description')

    def updateActions(self):
        super(FlourishGroupAddView, self).updateActions()
        self.actions['add'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

    @button.buttonAndHandler(_('Submit'), name='add')
    def handleAdd(self, action):
        super(FlourishGroupAddView, self).handleAdd.func(self, action)

    @button.buttonAndHandler(_('Cancel'))
    def handle_cancel_action(self, action):
        if 'camefrom' in self.request:
            url = self.request['camefrom']
            self.request.response.redirect(url)
            return
        app = ISchoolToolApplication(None)
        url = self.url_with_schoolyear_id(app, view_name='groups')
        self.request.response.redirect(url)

    def create(self, data):
        group = Group(data['title'], data.get('description'))
        form.applyChanges(self, group, data)
        return group

    def add(self, group):
        chooser = INameChooser(self.context)
        name = chooser.chooseName(u'', group)
        self.context[name] = group
        self._group = group
        return group

    def nextURL(self):
        return absoluteURL(self._group, self.request)

    @property
    def schoolyear(self):
        return ISchoolYear(self.context)

    @property
    def title(self):
        return _('Groups for ${schoolyear}',
                 mapping={'schoolyear': self.schoolyear.title})


class FlourishGroupEditView(flourish.form.Form, form.EditForm):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Group Information')
    fields = field.Fields(IGroup)
    fields = fields.select('title', 'description')

    @property
    def title(self):
        return self.context.title

    def update(self):
        return form.EditForm.update(self)

    @button.buttonAndHandler(_('Submit'), name='apply')
    def handleApply(self, action):
        super(FlourishGroupEditView, self).handleApply.func(self, action)
        # XXX: hacky sucessful submit check
        if (self.status == self.successMessage or
            self.status == self.noChangesMessage):
            url = absoluteURL(self.context, self.request)
            self.request.response.redirect(url)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        url = absoluteURL(self.context, self.request)
        self.request.response.redirect(url)

    def updateActions(self):
        super(FlourishGroupEditView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class FlourishGroupDeleteView(flourish.form.DialogForm, form.EditForm):
    """View used for confirming deletion of a group."""

    dialog_submit_actions = ('apply',)
    dialog_close_actions = ('cancel',)
    label = None

    @button.buttonAndHandler(_("Delete"), name='apply')
    def handleDelete(self, action):
        url = '%s/delete.html?delete.%s&CONFIRM' % (
            absoluteURL(self.context.__parent__, self.request),
            self.context.__name__)
        self.request.response.redirect(url)
        # We never have errors, so just close the dialog.
        self.ajax_settings['dialog'] = 'close'

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        pass

    def updateActions(self):
        super(FlourishGroupDeleteView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class GroupMembersTable(BasicPersonTable):

    prefix = "members"

    def items(self):
        return self.makeItems(self.context.members.int_ids)


class GroupLeadersTable(BasicPersonTable):

    prefix = "leaders"

    def items(self):
        return self.makeItems(self.context.leaders.int_ids)


class FlourishMemberViewPersons(EditPersonTemporalRelationships):
    """View class for adding / removing members to / from a group."""

    @property
    def app_states_name(self):
        if self.context.__name__ == 'students':
            return 'student-enrollment'
        return 'group-membership'

    @property
    def title(self):
        return self.context.title

    current_title = _("Current Members")
    available_title = _("Add Members")

    def getSelectedItems(self):
        members = EditPersonTemporalRelationships.getSelectedItems(self)
        return filter(IPerson.providedBy, members)

    def getCollection(self):
        return self.context.members


class FlourishManageGroupsOverview(flourish.page.Content,
                                   ActiveSchoolYearContentMixin):

    body_template = ViewPageTemplateFile(
        'templates/f_manage_groups_overview.pt')

    @property
    def groups(self):
        return IGroupContainer(self.schoolyear, None)

    def groups_url(self):
        return self.url_with_schoolyear_id(self.context, view_name='groups')


class FlourishRequestGroupIDCardsView(RequestRemoteReportDialog):

    report_builder = 'group_id_cards.pdf'
    report_task = OldReportTask


class FlourishGroupIDCardsView(FlourishPersonIDCardsViewBase):

    @property
    def title(self):
        return _('ID Cards for Group: ${group}',
                 mapping={'group': self.context.title})

    @property
    def filename(self):
        sy = ISchoolYear(self.context.__parent__)
        return 'id_cards_%s_%s.pdf' % (
            self.context.title,  sy.title)

    def persons(self):
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        sorted_persons = sorted(self.context.members, key=sorting_key)
        result = [self.getPersonData(person)
                  for person in sorted_persons]
        return result


def done_link_url_cell_formatter(group):
    def cell_formatter(value, item, formatter):
        group_url = absoluteURL(group, formatter.request)
        url = '%s?done_link=%s' % (absoluteURL(item, formatter.request),
                                   group_url)
        return '<a href="%s">%s</a>' % (url, value)
    return cell_formatter


class GroupAwarePersonTable(StatusPersonListTable):

    @property
    def app_states_name(self):
        if self.view.context.__name__ == 'students':
            return 'student-enrollment'
        return 'group-membership'

    def updateFormatter(self):
        group = self.view.context
        self.setUp(formatters=[done_link_url_cell_formatter(group),
                               done_link_url_cell_formatter(group)],
                   table_formatter=self.table_formatter,
                   batch_size=self.batch_size,
                   prefix=self.__name__,
                   css_classes={'table': 'data'})


class GroupAwarePersonTableFilter(PersonTableFilter):

    template = ViewPageTemplateFile('templates/f_group_aware_person_table_filter.pt')


class PersonGroupsTable(table.table.TableContent):

    group_by_column = 'schoolyear'

    @Lazy
    def source(self):
        int_ids = getUtility(IIntIds)
        source = dict([
                ('%s-%d' % (group.__name__, int_ids.getId(group)), group)
                for group in self.context.groups
                ])
        return source

    def columns(self):
        default = table.table.TableContent.columns(self)
        description = zc.table.column.GetterColumn(
            name='description',
            title=_('Description'),
            getter=lambda i, f: i.description or '',
            )
        schoolyear = SchoolYearColumn(
            name='schoolyear',
            title=_(u'School Year'),
            subsort=True)
        directlyProvides(schoolyear, ISortableColumn)
        return default + [description, schoolyear]


class PersonProfileGroupsPart(table.pdf.RMLTablePart):

    table_name = "groups_table"
    title = _("Group memberships")

