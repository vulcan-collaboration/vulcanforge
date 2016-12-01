import logging

from ming.odm.odmsession import ThreadLocalODMSession
from vulcanforge.migration.base import BaseMigration
from vulcanforge.project.model import MembershipInvitation
from vulcanforge.auth.model import User

LOG = logging.getLogger(__name__)


class FixProjectInvitations(BaseMigration):

    def _iter_invitations(self):
        q = {"email": {"$ne" : None}}
        cursor = MembershipInvitation.query.find(q)

        for invitation in cursor:
            if invitation.user_id is None:
                yield invitation

    def _fix_invitation(self, invite):
        p = invite.project
        if p is None or p.deleted:
            m = "Removing invitation for email {}. Project missing or deleted."
            LOG.info(m.format(invite.email))
            invite.delete()
        else:
            u = User.by_email_address(invite.email)
            if u and u.active():
                try:
                    is_member = p.get_membership_status(u) == 'member'
                    if is_member:
                        m = "Removing invitation for user {}.  Already member."
                        LOG.info(m.format(u.username))
                        invite.delete()
                    else:
                        invite.user_id = u._id
                        invite.email = None
                except:
                    msg = "Unable to membership status for user: {}"
                    LOG.exception(msg.format(u.username))

    def run(self):
        self.write_output('Repairing project invitations...')

        map(self._fix_invitation, self._iter_invitations())
        ThreadLocalODMSession.flush_all()

        self.write_output('Finished repairing project invitations.')
