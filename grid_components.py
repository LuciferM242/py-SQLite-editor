import wx
import wx.grid as gridlib
import sqlite3
from typing import Any, List, Tuple, Optional, Dict, Callable, Set

class SQLiteGridTable(gridlib.GridTableBase):
    """
    A custom GridTableBase to interface a wx.grid.Grid with an SQLite table.
    This class manages fetching, creating, updating, and deleting rows.
    """
    def __init__(self, db_conn: sqlite3.Connection, table_name: str):
        super().__init__()
        self.db_conn = db_conn; self.table_name = table_name; self.column_info: List[Tuple[str, str]] = []; self.col_names: List[str] = []; self.data: List[List[Any]] = []; self.original_data: List[List[Any]] = []; self.rows_to_delete: Set[Any] = set(); self.primary_key_col: Optional[str] = None; self.primary_key_index: int = -1
        self._type_converters: Dict[str, Callable[[Any], Any]] = {'int': int, 'integer': int, 'real': float, 'float': float, 'double': float}
        self._load_schema(); self.refresh_data()
    def _execute_query(self, query: str, params: tuple = ()) -> List[Any]:
        cursor = self.db_conn.cursor(); cursor.execute(query, params); return cursor.fetchall()
    def _load_schema(self):
        schema_info = self._execute_query(f"PRAGMA table_info('{self.table_name}')")
        self.column_info = [(col[1], col[2]) for col in schema_info]; self.col_names = [info[0] for info in self.column_info]
        for i, col in enumerate(schema_info):
            if col[5] == 1: self.primary_key_col = self.col_names[i]; self.primary_key_index = i; break
    def refresh_data(self):
        rows = self._execute_query(f"SELECT * FROM {self.table_name}"); self.data = [list(row) for row in rows]; self.original_data = [list(row) for row in self.data]; self.rows_to_delete.clear()
        if self.GetView(): self.GetView().ProcessTableMessage(gridlib.GridTableMessage(self, gridlib.GRIDTABLE_REQUEST_VIEW_GET_VALUES))
    def get_column_type(self, col: int) -> str:
        if 0 <= col < len(self.column_info): return self.column_info[col][1].upper()
        return ""
    def insert_row(self, at_row: int): self.data.insert(at_row, [None] * self.GetNumberCols())
    def process_row_deletion(self, at_row: int) -> bool:
        is_new_row = at_row >= len(self.original_data)
        if not is_new_row:
            if not self.has_primary_key(): return False
            pk_val = self.original_data[at_row][self.primary_key_index]; self.rows_to_delete.add(pk_val); self.original_data.pop(at_row)
        self.data.pop(at_row); return True
    def is_dirty(self) -> bool: return bool(self.rows_to_delete) or len(self.data) != len(self.original_data) or self.data != self.original_data
    def GetNumberRows(self) -> int: return len(self.data)
    def GetNumberCols(self) -> int: return len(self.col_names)
    def GetColLabelValue(self, col: int) -> str: return self.col_names[col]
    def has_primary_key(self) -> bool: return self.primary_key_col is not None
    def GetValue(self, row: int, col: int) -> str:
        try:
            value = self.data[row][col]; col_type = self.get_column_type(col); col_name = self.GetColLabelValue(col).lower()
            if 'BOOL' in col_type or ('INT' in col_type and (col_name.startswith('is_') or col_name.startswith('has_'))): return "1" if value else "0"
            return str(value) if value is not None else ''
        except IndexError: return ''
    def SetValue(self, row: int, col: int, value: str):
        try:
            col_type = self.column_info[col][1].lower()
            if value == '': self.data[row][col] = None; return
            converter = next((self._type_converters[key] for key in self._type_converters if key in col_type), str)
            self.data[row][col] = converter(value)
        except (ValueError, IndexError): pass
    def apply_changes(self) -> Tuple[bool, str]:
        if not self.is_dirty(): return True, "No changes to save."
        has_updates = any(self.data[i] != self.original_data[i] for i in range(len(self.original_data)))
        if not self.has_primary_key() and (self.rows_to_delete or has_updates): return False, "Cannot update or delete rows without a primary key."
        cursor = self.db_conn.cursor()
        try:
            if self.rows_to_delete:
                delete_query = f'DELETE FROM "{self.table_name}" WHERE "{self.primary_key_col}"=?'
                cursor.executemany(delete_query, [(pk,) for pk in self.rows_to_delete])
            set_clause = ", ".join(f'"{c}" = ?' for c in self.col_names)
            update_query = f'UPDATE "{self.table_name}" SET {set_clause} WHERE "{self.primary_key_col}"=?'
            insert_clause = ", ".join(f'"{c}"' for c in self.col_names)
            placeholders = ", ".join(['?'] * len(self.col_names))
            insert_query = f'INSERT INTO "{self.table_name}" ({insert_clause}) VALUES ({placeholders})'
            for i in range(len(self.original_data)):
                if self.data[i] != self.original_data[i]:
                    cursor.execute(update_query, tuple(self.data[i]) + (self.original_data[i][self.primary_key_index],))
            for i in range(len(self.original_data), len(self.data)):
                cursor.execute(insert_query, tuple(self.data[i]))
            self.db_conn.commit(); self.refresh_data(); return True, "Changes saved successfully."
        except sqlite3.Error as e: self.db_conn.rollback(); return False, f"Database error: {e}"

class DataTypeAwareGrid(gridlib.Grid):
    """A custom Grid that uses specific cell editors based on data type."""
    def __init__(self, parent): super().__init__(parent)
    def GetCellEditor(self, row: int, col: int) -> gridlib.GridCellEditor:
        table = self.GetTable()
        if not table: return super().GetCellEditor(row, col)
        col_type = table.get_column_type(col); col_name = table.GetColLabelValue(col).lower()
        if 'INT' in col_type or 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
            if 'INT' in col_type and (col_name.startswith('is_') or col_name.startswith('has_')): return gridlib.GridCellBoolEditor()
            return gridlib.GridCellNumberEditor()
        if 'BOOL' in col_type: return gridlib.GridCellBoolEditor()
        return super().GetCellEditor(row, col)