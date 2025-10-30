from typing import Dict

class DataExporter:
    """Export parsed data to various formats"""
    
    @staticmethod
    def to_json(data: Dict, output_path: str):
        """Export to JSON"""
        import json
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def to_csv(data: Dict, output_path: str):
        """Export tabular data to CSV"""
        import csv
        
        # Extract flattened data
        rows = []
        
        # Add specifications
        if 'universal_data' in data and 'specification' in data['universal_data']:
            for spec in data['universal_data']['specification']:
                rows.append({
                    'Category': 'Specification',
                    'Type': spec.get('type'),
                    'Value': spec.get('value'),
                    'Unit': spec.get('unit'),
                    'Context': spec.get('context', '')[:100]
                })
        
        # Write to CSV
        if rows:
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
    
    @staticmethod
    def to_excel(data: Dict, output_path: str):
        """Export to Excel with multiple sheets"""
        try:
            import pandas as pd
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Title block sheet
                if 'universal_data' in data and 'titleblock' in data['universal_data']:
                    tb_df = pd.DataFrame([data['universal_data']['titleblock']])
                    tb_df.to_excel(writer, sheet_name='Title Block', index=False)
                
                # Specifications sheet
                if 'universal_data' in data and 'specification' in data['universal_data']:
                    specs_df = pd.DataFrame(data['universal_data']['specification'])
                    specs_df.to_excel(writer, sheet_name='Specifications', index=False)
                
                # Notes sheet
                if 'universal_data' in data and 'notes' in data['universal_data']:
                    notes_df = pd.DataFrame(data['universal_data']['notes'])
                    notes_df.to_excel(writer, sheet_name='Notes', index=False)
        
        except ImportError:
            print("pandas and openpyxl required for Excel export")
    
    @staticmethod
    def to_database(data: Dict, db_connection):
        """Export to database (example with SQLite)"""
        import sqlite3
        
        cursor = db_connection.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drawings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_number TEXT,
                title TEXT,
                drawing_type TEXT,
                discipline TEXT,
                scale TEXT,
                date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_id INTEGER,
                spec_type TEXT,
                value TEXT,
                unit TEXT,
                context TEXT,
                FOREIGN KEY (drawing_id) REFERENCES drawings(id)
            )
        ''')
        
        # Insert drawing
        title_block = data.get('universal_data', {}).get('titleblock', {})
        classification = data.get('classification', {})
        
        cursor.execute('''
            INSERT INTO drawings (drawing_number, title, drawing_type, discipline, scale, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            title_block.get('drawing_number'),
            title_block.get('drawing_title'),
            classification.get('type'),
            classification.get('discipline'),
            title_block.get('scale'),
            title_block.get('date')
        ))
        
        drawing_id = cursor.lastrowid
        
        # Insert specifications
        specs = data.get('universal_data', {}).get('specification', [])
        for spec in specs:
            cursor.execute('''
                INSERT INTO specifications (drawing_id, spec_type, value, unit, context)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                drawing_id,
                spec.get('type'),
                spec.get('value'),
                spec.get('unit'),
                spec.get('context', '')[:500]  # Truncate long context
            ))
        
        db_connection.commit()