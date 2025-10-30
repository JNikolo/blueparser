
from typing import Dict, List
from extractors.BaseExtractor import BaseExtractor


class TableExtractor(BaseExtractor):
    """Extract tabular data"""
    
    def extract(self, text_items: List[Dict], zones: Dict) -> List[Dict]:
        """
        Extract tables using spatial clustering
        """
        # Group items by approximate row (y-coordinate)
        rows = self._cluster_by_rows(text_items)
        
        # For each row, group by columns (x-coordinate)
        tables = []
        current_table = []
        
        for row_items in rows:
            columns = self._cluster_by_columns(row_items)
            
            # If we have consistent number of columns, it's likely a table
            if len(columns) >= 2:
                current_table.append(columns)
            else:
                if current_table and len(current_table) >= 2:
                    tables.append(self._format_table(current_table))
                current_table = []
        
        # Don't forget last table
        if current_table and len(current_table) >= 2:
            tables.append(self._format_table(current_table))
        
        return tables
    
    def _cluster_by_rows(self, items: List[Dict], tolerance: float = 0.02) -> List[List[Dict]]:
        """Group items that are on the same horizontal line"""
        if not items:
            return []
        
        # Sort by y-coordinate
        sorted_items = sorted(items, key=lambda x: x['bbox']['top'])
        
        rows = []
        current_row = [sorted_items[0]]
        current_y = sorted_items[0]['bbox']['top']
        
        for item in sorted_items[1:]:
            if abs(item['bbox']['top'] - current_y) < tolerance:
                current_row.append(item)
            else:
                rows.append(current_row)
                current_row = [item]
                current_y = item['bbox']['top']
        
        rows.append(current_row)
        return rows
    
    def _cluster_by_columns(self, items: List[Dict]) -> List[str]:
        """Group items into columns based on x-coordinate"""
        # Sort by x-coordinate
        sorted_items = sorted(items, key=lambda x: x['bbox']['left'])
        return [item['text'] for item in sorted_items]
    
    def _format_table(self, table_data: List[List[str]]) -> Dict:
        """Convert clustered data into structured table"""
        if not table_data:
            return {}
        
        # First row is likely headers
        headers = table_data[0]
        rows = table_data[1:]
        
        return {
            'headers': headers,
            'rows': rows,
            'row_count': len(rows),
            'column_count': len(headers)
        }