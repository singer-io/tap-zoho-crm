import sys
import unittest
from unittest.mock import patch, MagicMock


class TestDoDiscover(unittest.TestCase):

    @patch('tap_zoho_crm.json.dump')
    @patch('tap_zoho_crm.discover')
    def test_do_discover_calls_discover_and_dumps_catalog(self, mock_discover, mock_json_dump):
        """Test that do_discover calls discover() and dumps the catalog to stdout."""
        from tap_zoho_crm import do_discover

        mock_catalog = MagicMock()
        mock_catalog.to_dict.return_value = {"streams": []}
        mock_discover.return_value = mock_catalog
        mock_client = MagicMock()

        result = do_discover(mock_client)

        mock_discover.assert_called_once_with(client=mock_client)
        mock_json_dump.assert_called_once_with({"streams": []}, sys.stdout, indent=2)
        self.assertEqual(result, mock_catalog)


class TestMain(unittest.TestCase):

    @patch('tap_zoho_crm.do_discover')
    @patch('tap_zoho_crm.Client')
    @patch('singer.utils.parse_args')
    def test_main_discover_mode(self, mock_parse_args, mock_client_cls, mock_do_discover):
        """Test main() runs discover mode when --discover flag is set."""
        from tap_zoho_crm import main

        mock_args = MagicMock()
        mock_args.discover = True
        mock_args.catalog = None
        mock_args.state = None
        mock_args.config = {}
        mock_parse_args.return_value = mock_args

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        main()

        mock_do_discover.assert_called_once_with(client=mock_client)

    @patch('tap_zoho_crm.sync')
    @patch('tap_zoho_crm.Client')
    @patch('singer.utils.parse_args')
    def test_main_sync_mode_with_state(self, mock_parse_args, mock_client_cls, mock_sync):
        """Test main() runs sync when catalog is provided and state is truthy."""
        from tap_zoho_crm import main

        mock_catalog = MagicMock()
        mock_state = {'bookmarks': {'stream': '2020-01-01'}}
        mock_config = {'client_id': 'x'}

        mock_args = MagicMock()
        mock_args.discover = False
        mock_args.catalog = mock_catalog
        mock_args.state = mock_state
        mock_args.config = mock_config
        mock_parse_args.return_value = mock_args

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        main()

        mock_sync.assert_called_once_with(
            client=mock_client,
            config=mock_config,
            catalog=mock_catalog,
            state=mock_state
        )

    @patch('tap_zoho_crm.sync')
    @patch('tap_zoho_crm.Client')
    @patch('singer.utils.parse_args')
    def test_main_sync_mode_no_state(self, mock_parse_args, mock_client_cls, mock_sync):
        """Test main() uses empty dict when no state is provided."""
        from tap_zoho_crm import main

        mock_catalog = MagicMock()

        mock_args = MagicMock()
        mock_args.discover = False
        mock_args.catalog = mock_catalog
        mock_args.state = None
        mock_args.config = {}
        mock_parse_args.return_value = mock_args

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        main()

        mock_sync.assert_called_once_with(
            client=mock_client,
            config={},
            catalog=mock_catalog,
            state={}
        )

    def test_main_module_name_guard(self):
        """Cover the 'if __name__ == __main__' block by executing __init__.py as __main__."""
        import runpy
        import tap_zoho_crm
        import os
        init_path = os.path.join(
            os.path.dirname(tap_zoho_crm.__file__), '__init__.py'
        )
        with patch('singer.utils.parse_args') as mock_parse_args, \
             patch('tap_zoho_crm.client.Client') as mock_client_cls, \
             patch('tap_zoho_crm.discover.discover') as mock_discover:
            mock_args = MagicMock()
            mock_args.discover = True
            mock_args.catalog = None
            mock_args.state = None
            mock_args.config = {}
            mock_parse_args.return_value = mock_args

            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_catalog = MagicMock()
            mock_catalog.to_dict.return_value = {"streams": []}
            mock_discover.return_value = mock_catalog

            runpy.run_path(init_path, run_name='__main__')
