import wx
import wx.grid as gridlib
import sqlite3
import csv
from cytolk import tolk
from typing import Optional, Tuple

from grid_components import SQLiteGridTable, DataTypeAwareGrid

# --- Constants ---
APP_TITLE = 'SQLite Editor'
APP_VENDOR = 'SQLiteEditor'
WELCOME_MESSAGE = (
    "Welcome to SQLite Editor!\n\n"
    "Please select a file by choosing 'Open' from the 'File' menu (Ctrl+O)."
)

class SQLiteEditor(wx.Frame):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.db_conn: Optional[sqlite3.Connection] = None
        self.edit_mode: bool = False
        self.last_spoken_cell: Tuple[Optional[int], Optional[int]] = (None, None)
        self.grid_table: Optional[SQLiteGridTable] = None
        self.config = wx.Config(APP_TITLE, APP_VENDOR)
        self.file_history = wx.FileHistory(9)
        self.file_history.Load(self.config)
        self._init_ui()
        self._update_ui_state(has_db=False)
        self.Centre()
        self.welcome_message.SetFocus()
    def _init_ui(self):
        self.SetTitle(APP_TITLE)
        self.SetSize((900, 700))
        self.statusBar = self.CreateStatusBar(3)
        self.statusBar.SetStatusWidths([-3, -2, -1])
        panel = wx.Panel(self)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self._create_menu()
        self.welcome_message = wx.StaticText(panel, label=WELCOME_MESSAGE, style=wx.ALIGN_CENTER)
        font = self.welcome_message.GetFont(); font.SetPointSize(14); font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.welcome_message.SetFont(font)
        self.main_sizer.Add(self.welcome_message, 1, wx.EXPAND | wx.ALL, 20)
        table_sizer = wx.BoxSizer(wx.HORIZONTAL); self.table_list_label = wx.StaticText(panel, label="Select Table:")
        self.table_list = wx.ComboBox(panel, style=wx.CB_READONLY | wx.CB_SORT)
        self.current_table_display = wx.StaticText(panel, label="")
        table_sizer.Add(self.table_list_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        table_sizer.Add(self.table_list, 1, wx.EXPAND | wx.RIGHT, 10)
        table_sizer.Add(self.current_table_display, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        self.main_sizer.Add(table_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.data_grid = DataTypeAwareGrid(panel)
        self.data_grid.EnableEditing(False)
        self.main_sizer.Add(self.data_grid, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(self.main_sizer)
        self._bind_events()

    def _create_menu(self):
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Open...\tCtrl+O")
        self.export_csv_item = file_menu.Append(wx.ID_ANY, "Export to CSV...", "Export the current table to a CSV file")
        self.save_item = file_menu.Append(wx.ID_SAVE, "&Save Changes\tCtrl+S")
        file_menu.AppendSeparator()
        recent_files_menu = wx.Menu()
        self.file_history.UseMenu(recent_files_menu)
        self.file_history.AddFilesToMenu(recent_files_menu)
        file_menu.AppendSubMenu(recent_files_menu, "&Recent Files")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "&Quit\tCtrl+Q")
        menubar.Append(file_menu, "&File")
        edit_menu = wx.Menu()
        self.toggle_edit_item = edit_menu.AppendCheckItem(wx.ID_EDIT, "Enable &Editing")
        edit_menu.AppendSeparator()
        self.add_row_item = edit_menu.Append(wx.ID_ADD, "Add Row\tCtrl+N")
        self.delete_row_item = edit_menu.Append(wx.ID_DELETE, "Delete Row\tCtrl+D")
        menubar.Append(edit_menu, "&Edit")
        view_menu = wx.Menu()
        self.view_schema_item = view_menu.Append(wx.ID_ANY, "View Table Schema")
        menubar.Append(view_menu, "&View")
        self.SetMenuBar(menubar)

    def _bind_events(self):
        self.Bind(wx.EVT_CLOSE, self.on_quit)
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_save_changes, self.save_item)
        self.Bind(wx.EVT_MENU, self.on_quit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.on_toggle_edit_mode, self.toggle_edit_item)
        self.Bind(wx.EVT_MENU, self.on_add_row, self.add_row_item)
        self.Bind(wx.EVT_MENU, self.on_delete_row, self.delete_row_item)
        self.Bind(wx.EVT_MENU, self.on_view_schema, self.view_schema_item)
        self.Bind(wx.EVT_MENU, self.on_export_csv, self.export_csv_item)
        self.Bind(wx.EVT_MENU_RANGE, self.on_file_history, id=wx.ID_FILE1, id2=wx.ID_FILE9)
        self.table_list.Bind(wx.EVT_COMBOBOX, self.on_table_selected)
        self.data_grid.Bind(gridlib.EVT_GRID_CELL_CHANGING, self.on_grid_cell_changing)
        self.data_grid.Bind(gridlib.EVT_GRID_SELECT_CELL, self.on_grid_select_cell)
        self.data_grid.Bind(gridlib.EVT_GRID_EDITOR_CREATED, self.on_grid_editor_created)
        self.data_grid.Bind(wx.EVT_KEY_DOWN, self.on_grid_key_down)

    def _update_ui_state(self, has_db: bool, has_tables: bool = False):
        self.welcome_message.Show(not has_db)
        is_data_visible = has_db and has_tables
        self.data_grid.Show(is_data_visible); self.table_list_label.Show(has_db); self.table_list.Show(has_db); self.current_table_display.Show(has_db)
        self.save_item.Enable(is_data_visible); self.toggle_edit_item.Enable(is_data_visible); self.add_row_item.Enable(is_data_visible and self.edit_mode)
        self.delete_row_item.Enable(is_data_visible and self.edit_mode); self.view_schema_item.Enable(is_data_visible); self.export_csv_item.Enable(is_data_visible)
        self.main_sizer.Layout()

    def on_open(self, event: wx.CommandEvent):
        if self._check_unsaved_changes() == wx.ID_CANCEL: return
        wildcard = "SQLite files (*.sqlite;*.db;*.db3)|*.sqlite;*.db;*.db3|All files (*.*)|*.*"
        with wx.FileDialog(self, "Open SQLite file", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            self._load_database(dlg.GetPath())
            
    def on_file_history(self, event: wx.CommandEvent):
        file_index = event.GetId() - wx.ID_FILE1
        path = self.file_history.GetHistoryFile(file_index)
        if self._check_unsaved_changes() == wx.ID_CANCEL: return
        self.file_history.AddFileToHistory(path)
        self._load_database(path)

    def on_export_csv(self, event: wx.CommandEvent):
        if not self.grid_table: tolk.speak("No table loaded to export."); return
        table_name = self.grid_table.table_name
        with wx.FileDialog(self, "Export to CSV", wildcard="CSV files (*.csv)|*.csv", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, defaultFile=f"{table_name}.csv") as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            pathname = dlg.GetPath()
            try:
                with open(pathname, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.grid_table.col_names)
                    writer.writerows(self.grid_table.data)
                self._update_statusbar(f"Successfully exported to {pathname}")
                tolk.speak("Export successful.")
            except IOError as e:
                wx.MessageBox(f"Error exporting file: {e}", "Export Error", wx.OK | wx.ICON_ERROR)
                tolk.speak("Export failed.")
                
    def _load_database(self, path: str):
        try:
            if self.db_conn: self.db_conn.close()
            self.db_conn = sqlite3.connect(path); cursor = self.db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [table[0] for table in cursor.fetchall()]
            self.SetTitle(f"{APP_TITLE} - {path.split('/')[-1]}")
            self.file_history.AddFileToHistory(path)
            self.file_history.Save(self.config)
            self._update_statusbar("Database loaded", path, "")
            if not tables:
                tolk.speak("Database loaded, but no tables were found."); self.grid_table = None
                self._update_ui_state(has_db=True, has_tables=False); self.table_list.Clear()
                if self.data_grid.GetTable(): self.data_grid.SetTable(None, takeOwnership=True)
                return
            tolk.speak(f"Connected. {len(tables)} tables found."); self.table_list.Set(tables)
            self.table_list.SetSelection(0); self._load_table_data(tables[0])
            self._update_ui_state(has_db=True, has_tables=True)
        except sqlite3.Error as e:
            wx.MessageBox(f"Error opening database: {e}", "Database Error", wx.OK | wx.ICON_ERROR)
            self.db_conn = None; self.SetTitle(APP_TITLE)
            self._update_ui_state(has_db=False)
            
    def on_quit(self, event: wx.Event):
        if self._check_unsaved_changes() == wx.ID_CANCEL:
            if isinstance(event, wx.CloseEvent): event.Veto()
            return
        self.file_history.Save(self.config)
        self.config.Flush()
        if self.db_conn: self.db_conn.close()
        self.Destroy()

    def _update_statusbar(self, main: str, db_path: Optional[str]=None, table_info: Optional[str]=None): self.statusBar.SetStatusText(main, 0); self.statusBar.SetStatusText(db_path or self.statusBar.GetStatusText(1), 1); self.statusBar.SetStatusText(table_info or self.statusBar.GetStatusText(2), 2)
    def _check_unsaved_changes(self) -> Optional[int]:
        if not (self.grid_table and self.grid_table.is_dirty()): return wx.ID_NO
        dlg = wx.MessageDialog(self, "You have unsaved changes. Would you like to save them?", "Unsaved Changes", wx.YES_NO | wx.CANCEL | wx.ICON_WARNING)
        result = dlg.ShowModal(); dlg.Destroy()
        if result == wx.ID_YES:
            self.on_save_changes(None)
            if self.grid_table and self.grid_table.is_dirty(): return wx.ID_CANCEL
        return result
    def on_table_selected(self, event: Optional[wx.CommandEvent]):
        if self._check_unsaved_changes() == wx.ID_CANCEL:
            if self.grid_table: self.table_list.SetStringSelection(self.grid_table.table_name)
            return
        table_name = self.table_list.GetStringSelection()
        if table_name: self._load_table_data(table_name)
    def _load_table_data(self, table_name: str):
        if not self.db_conn: return
        try:
            self.grid_table = SQLiteGridTable(self.db_conn, table_name)
            self.data_grid.SetTable(self.grid_table, takeOwnership=True)
            self.data_grid.AutoSizeColumns(); self.data_grid.ForceRefresh()
            self.current_table_display.SetLabel(f"Current Table: {table_name}")
            rows, cols = self.grid_table.GetNumberRows(), self.grid_table.GetNumberCols()
            self._update_statusbar(f"Loaded table: {table_name}", None, f"{rows} rows, {cols} columns")
            tolk.speak(f"Loaded table: {table_name}."); self.data_grid.GoToCell(0, 0)
        except Exception as e: wx.MessageBox(f"Error loading table '{table_name}': {e}", "Error", wx.OK | wx.ICON_ERROR)
    def on_toggle_edit_mode(self, event: wx.CommandEvent):
        self.edit_mode = event.IsChecked(); self.data_grid.EnableEditing(self.edit_mode)
        tolk.speak(f"Edit mode {'enabled' if self.edit_mode else 'disabled'}.")
        self._update_ui_state(has_db=self.db_conn is not None, has_tables=self.table_list.GetCount() > 0)
        if not self.edit_mode and self.data_grid.IsCellEditControlShown(): self.data_grid.HideCellEditControl()
    def on_save_changes(self, event: Optional[wx.CommandEvent]):
        if not self.grid_table: return
        if self.data_grid.IsCellEditControlShown(): self.data_grid.HideCellEditControl()
        success, message = self.grid_table.apply_changes()
        tolk.speak(message); self._update_statusbar(message)
        if success:
            self.data_grid.ProcessTableMessage(gridlib.GridTableMessage(self.grid_table, gridlib.GRIDTABLE_REQUEST_VIEW_GET_VALUES))
            self.data_grid.ForceRefresh()
        else: wx.MessageBox(message, "Save Failed", wx.OK | wx.ICON_ERROR)
    def on_add_row(self, event: wx.CommandEvent):
        if not self.grid_table: return
        insert_pos = self.data_grid.GetGridCursorRow() + 1
        self.grid_table.insert_row(insert_pos)
        msg = gridlib.GridTableMessage(self.grid_table, gridlib.GRIDTABLE_NOTIFY_ROWS_INSERTED, insert_pos, 1)
        self.data_grid.ProcessTableMessage(msg)
        tolk.speak(f"Added new row at position {insert_pos + 1}")
        self._update_statusbar("Row added. Save changes to commit.")
    def on_delete_row(self, event: wx.CommandEvent):
        if not self.grid_table or self.data_grid.GetNumberRows() == 0: return
        row_to_delete = self.data_grid.GetGridCursorRow(); current_col = self.data_grid.GetGridCursorCol()
        dlg = wx.MessageDialog(self, f"Are you sure you want to delete row {row_to_delete + 1}?", "Confirm Deletion", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        if dlg.ShowModal() != wx.ID_YES: dlg.Destroy(); return
        dlg.Destroy()
        if self.grid_table.process_row_deletion(row_to_delete):
            msg = gridlib.GridTableMessage(self.grid_table, gridlib.GRIDTABLE_NOTIFY_ROWS_DELETED, row_to_delete, 1)
            self.data_grid.ProcessTableMessage(msg)
            new_cursor_row = max(0, row_to_delete - 1)
            self.data_grid.SetGridCursor(new_cursor_row, current_col)
            tolk.speak(f"Row {row_to_delete + 1} deleted."); self._update_statusbar("Row deleted. Save changes to commit.")
        else: tolk.speak("Could not delete row.")
    def on_view_schema(self, event: wx.CommandEvent):
        if not self.grid_table or not self.db_conn: tolk.speak("No table is loaded."); return
        try:
            table_name = self.grid_table.table_name
            cursor = self.db_conn.cursor(); cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)); result = cursor.fetchone()
            if result and result[0]:
                schema = result[0]
                dlg = wx.MessageDialog(self, f"Schema for table '{table_name}':\n\n{schema}", "Table Schema", wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal(); dlg.Destroy(); tolk.speak(f"Schema for table {table_name}: {schema}")
            else: wx.MessageBox(f"Could not retrieve schema for table '{table_name}'.", "Error", wx.OK | wx.ICON_ERROR); tolk.speak("Could not retrieve schema.")
        except sqlite3.Error as e: wx.MessageBox(f"Database error: {e}", "Error", wx.OK | wx.ICON_ERROR); tolk.speak(f"Database error: {e}")
    def on_grid_cell_changing(self, event: gridlib.GridEvent):
        if not self.edit_mode: event.Veto(); return
        event.Skip()
    def on_grid_select_cell(self, event: gridlib.GridEvent):
        row, col = event.GetRow(), event.GetCol()
        if (row, col) == self.last_spoken_cell: event.Skip(); return
        self.last_spoken_cell = (row, col)
        if self.grid_table:
            col_name = self.grid_table.GetColLabelValue(col); data_type = self.grid_table.get_column_type(col)
            value_str = self.grid_table.GetValue(row, col) or "empty"
            tolk.speak(f"{col_name}, Type {data_type}, Row {row + 1}, {value_str}")
        event.Skip()
    def on_grid_editor_created(self, event: gridlib.GridEvent):
        row, col = event.GetRow(), event.GetCol()
        if self.grid_table:
            col_name = self.grid_table.GetColLabelValue(col); value_str = self.data_grid.GetCellValue(row, col) or "empty"
            tolk.speak(f"Editing {col_name}. Current value: {value_str}")
        event.Skip()
    def on_grid_key_down(self, event: wx.KeyEvent):
        if event.GetKeyCode() == wx.WXK_F2 and not self.edit_mode: tolk.speak("Edit mode is disabled."); return
        event.Skip()