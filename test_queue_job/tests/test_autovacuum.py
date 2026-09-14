# Copyright 2019 Versada UAB
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).

from datetime import datetime, timedelta

from .common import JobCommonCase


class TestQueueJobAutovacuumCronJob(JobCommonCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cron_job = cls.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")

    def test_old_jobs_are_deleted_by_cron_job(self):
        """Old jobs are deleted by the autovacuum cron job."""
        date_done = datetime.now() - timedelta(
            days=self.queue_job._removal_interval + 1
        )
        stored = self._create_job()
        stored.write({"date_done": date_done})
        self.cron_job.method_direct_trigger()
        self.assertFalse(stored.exists())

    def test_autovacuum(self):
        # test default removal interval
        stored = self._create_job()
        date_done = datetime.now() - timedelta(days=29)
        stored.write({"date_done": date_done})
        self.env["queue.job"].autovacuum()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 1
        )

        date_done = datetime.now() - timedelta(days=31)
        stored.write({"date_done": date_done})
        self.env["queue.job"].autovacuum()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 0
        )

    def test_autovacuum_multi_channel(self):
        root_channel = self.env.ref("queue_job.channel_root")
        channel_60days = self.env["queue.job.channel"].create(
            {"name": "60days", "removal_interval": 60, "parent_id": root_channel.id}
        )
        date_done = datetime.now() - timedelta(days=31)
        job_root = self._create_job()
        job_root.write({"date_done": date_done})
        job_60days = self._create_job()
        job_60days.write(
            {"channel": channel_60days.complete_name, "date_done": date_done}
        )

        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 2
        )
        self.env["queue.job"].autovacuum()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 1
        )

        date_done = datetime.now() - timedelta(days=61)
        job_60days.write({"date_done": date_done})
        self.env["queue.job"].autovacuum()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 0
        )

    def test_dynamic_subchannel_uses_nearest_configured_retention(self):
        root = self.env.ref("queue_job.channel_root")
        child = self.env["queue.job.channel"].create(
            {"name": "retained", "removal_interval": 60, "parent_id": root.id}
        )
        retained = self._create_job()
        retained.write(
            {
                "channel": child.complete_name + ".dynamic",
                "date_done": datetime.now() - timedelta(days=31),
            }
        )
        expired = self._create_job()
        expired.write(
            {
                "channel": root.complete_name + ".dynamic",
                "date_done": datetime.now() - timedelta(days=31),
            }
        )
        self.queue_job.autovacuum()
        self.assertTrue(retained.exists())
        self.assertFalse(expired.exists())
        retained.date_done = datetime.now() - timedelta(days=61)
        self.queue_job.autovacuum()
        self.assertFalse(retained.exists())
