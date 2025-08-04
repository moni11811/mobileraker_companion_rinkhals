import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from mobileraker.data.dtos.moonraker.printer_objects import (
    DisplayStatus,
    PrintStats,
    ServerInfo,
    VirtualSDCard,
)
from mobileraker.service.data_sync_service import DataSyncService


class TestDataSyncService(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()

        self.jrpc_new = MagicMock()
        self.jrpc_new.send_and_receive_method = AsyncMock(return_value=({"result": {}}, None))
        self.jrpc_new.send_method = AsyncMock(return_value=None)
        self.data_sync_service_new = DataSyncService(self.jrpc_new, "Printer", self.loop, 2)

        self.jrpc_legacy = MagicMock()
        self.jrpc_legacy.send_and_receive_method = AsyncMock(return_value=({"result": {}}, None))
        self.jrpc_legacy.send_method = AsyncMock(return_value=None)
        self.data_sync_service_legacy = DataSyncService(self.jrpc_legacy, self.loop, 2)

    def services(self):
        return [
            ("new", self.data_sync_service_new, self.jrpc_new),
            ("legacy", self.data_sync_service_legacy, self.jrpc_legacy),
        ]

    def test_initialization(self):
        for name, svc, _ in self.services():
            with self.subTest(signature=name):
                self.assertFalse(svc.klippy_ready)
                self.assertIsInstance(svc.server_info, ServerInfo)
                self.assertIsInstance(svc.print_stats, PrintStats)
                self.assertIsInstance(svc.display_status, DisplayStatus)
                self.assertIsInstance(svc.virtual_sdcard, VirtualSDCard)

    def test_legacy_signature_defaults_printer_name(self):
        self.assertEqual(
            self.data_sync_service_legacy._logger.name,
            "mobileraker._Default.sync",
        )

    def test_parse_objects_with_print_stats(self):
        status_objects = {
            "print_stats": {"filename": "test.gcode", "state": "printing"}
        }
        for name, svc, _ in self.services():
            with self.subTest(signature=name):
                svc._parse_objects(status_objects)
                self.assertEqual(svc.print_stats.filename, "test.gcode")
                self.assertEqual(svc.print_stats.state, "printing")

    def test_parse_objects_with_display_status(self):
        status_objects = {
            "display_status": {"message": "Printing in progress"}
        }
        for name, svc, _ in self.services():
            with self.subTest(signature=name):
                svc._parse_objects(status_objects)
                self.assertEqual(svc.display_status.message, "Printing in progress")

    def test_parse_objects_with_virtual_sdcard(self):
        status_objects = {
            "virtual_sdcard": {"progress": 0.5}
        }
        for name, svc, _ in self.services():
            with self.subTest(signature=name):
                svc._parse_objects(status_objects)
                self.assertEqual(svc.virtual_sdcard.progress, 0.5)

    def test_parse_objects_with_all_status_objects(self):
        status_objects = {
            "print_stats": {"filename": "test.gcode", "state": "printing"},
            "display_status": {"message": "Printing in progress"},
            "virtual_sdcard": {"progress": 0.5},
        }
        for name, svc, _ in self.services():
            with self.subTest(signature=name):
                svc._parse_objects(status_objects)
                self.assertEqual(svc.print_stats.filename, "test.gcode")
                self.assertEqual(svc.print_stats.state, "printing")
                self.assertEqual(svc.display_status.message, "Printing in progress")
                self.assertEqual(svc.virtual_sdcard.progress, 0.5)

    def test_parse_objects_with_no_status_objects(self):
        status_objects = {}
        for name, svc, _ in self.services():
            with self.subTest(signature=name):
                svc._parse_objects(status_objects)
                self.assertIsNone(svc.print_stats.filename)
                self.assertEqual(svc.print_stats.state, "error")
                self.assertIsNone(svc.display_status.message)
                self.assertEqual(svc.virtual_sdcard.progress, 0)

    def test_resync_with_parse_objects(self):
        status_objects = {
            "print_stats": {"filename": "test.gcode", "state": "printing"},
            "display_status": {"message": "Printing in progress"},
            "virtual_sdcard": {"progress": 0.5},
        }

        for name, svc, jrpc in self.services():
            async def mock_send_and_receive_method(method, params=None):
                if method == "server.info":
                    return {"result": {"klippy_state": "ready"}}, None
                elif method == "printer.objects.list":
                    return {"result": {"objects": list(status_objects.keys())}}, None
                elif method == "printer.objects.query":
                    return {"result": {"status": status_objects}}, None
                elif method == "server.files.metadata":
                    return {"result": {}}, None

            jrpc.send_and_receive_method.side_effect = mock_send_and_receive_method

            with self.subTest(signature=name):
                self.loop.run_until_complete(svc.resync())
                self.assertEqual(svc.print_stats.filename, "test.gcode")
                self.assertEqual(svc.print_stats.state, "printing")
                self.assertEqual(svc.display_status.message, "Printing in progress")
                self.assertEqual(svc.virtual_sdcard.progress, 0.5)

    def test_resync_klippy_ready(self):
        for name, svc, jrpc in self.services():
            async def mock_send_and_receive_method(method, params=None):
                if method == "server.info":
                    return {"result": {"klippy_state": "ready"}}, None
                elif method == "printer.objects.list":
                    return {"result": {"objects": []}}, None
                elif method == "printer.objects.query":
                    return {"result": {"status": {}}}, None
                elif method == "server.files.metadata":
                    return {"result": {}}, None

            jrpc.send_and_receive_method.side_effect = mock_send_and_receive_method

            with self.subTest(signature=name):
                self.loop.run_until_complete(svc.resync())
                self.assertTrue(svc.klippy_ready)

    # def test_resync_klippy_not_ready(self):
    #     # Test resync when Klippy is not ready and then becomes ready after a few retries
    #     async def mock_non_ready(method, params=None):
    #         return {"result": {"klippy_state": "not_ready"}}, None

    #     async def mock_ready(method, params=None):
    #         return {"result": {"klippy_state": "not_ready"}}, None

    #     async def mock_printer_query(method, params=None):
    #         return {"result": {"status": {}}}, None

    #     self.jrpc.send_and_receive_method.side_effect = [
    #         mock_non_ready, mock_ready, mock_printer_query]

    #     # Run resync and assert that it eventually becomes ready after retries
    #     self.loop.run_until_complete(self.data_sync_service.resync())
    #     self.assertTrue(self.data_sync_service.klippy_ready)

    def test_resync_klippy_not_ready_timeout(self):
        for name, svc, jrpc in self.services():
            async def mock_send_and_receive_method(method, params=None):
                if method == "server.info":
                    return {"result": {"klippy_state": "not_ready"}}, None

            jrpc.send_and_receive_method.side_effect = mock_send_and_receive_method

            with self.subTest(signature=name):
                with self.assertRaises(TimeoutError):
                    self.loop.run_until_complete(svc.resync())

    # Add more test cases for other methods as needed

    # Add more unit tests for other methods if needed


if __name__ == '__main__':
    unittest.main()
