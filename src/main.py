from DrawingParser import DrawingParser
from DrawingValidator import DrawingValidator
from DataExporter import DataExporter
from pathlib import Path

def main():
    # Initialize parser
    parser = DrawingParser()
    validator = DrawingValidator()
    exporter = DataExporter()

    # Use absolute paths based on script location
    script_dir = Path(__file__).parent.parent
    basePath = (script_dir / "data").resolve()
    outputPath = (script_dir / "outputs").resolve()
    outputPath.mkdir(parents=True, exist_ok=True)
    
    # List of drawings to parse
    drawings = [
        basePath / "Duplex_Pump_Station_Mechanical_Drawings.pdf",
        basePath / "C-16 - Sanitary Sewer Standard Details.pdf",
        # Add more drawings...
    ]
    
    for drawing_path in drawings:
        print(f"\n{'='*60}")
        print(f"Processing: {drawing_path}")
        print(f"{'='*60}")
        
        try:
            # Parse
            result = parser.parse(str(drawing_path), ocr_method='textract')
            
            # Validate
            validation = validator.validate(result)
            
            if not validation.is_valid:
                print(f"❌ Validation failed:")
                for error in validation.errors:
                    print(f"   ERROR: {error}")
            
            if validation.warnings:
                print(f"⚠️  Warnings:")
                for warning in validation.warnings:
                    print(f"   WARNING: {warning}")
            
            # Print summary
            print(f"\n📊 Summary:")
            print(f"   Type: {result['classification']['type']}")
            print(f"   Discipline: {result['classification']['discipline']}")
            print(f"   Confidence: {result['classification']['confidence']:.2f}")
            
            if result['universal_data'].get('titleblock'):
                tb = result['universal_data']['titleblock']
                print(f"   Drawing #: {tb.get('drawing_number', 'N/A')}")
                print(f"   Title: {tb.get('drawing_title', 'N/A')}")
            
            if result['universal_data'].get('specification'):
                specs = result['universal_data']['specification']
                print(f"   Specifications found: {len(specs)}")
            
            if result['universal_data'].get('notes'):
                notes = result['universal_data']['notes']
                print(f"   Notes found: {len(notes)}")
            
            # Export
            base_name = drawing_path.stem
            exporter.to_json(result, outputPath / f"{base_name}_parsed.json")
            exporter.to_csv(result, outputPath / f"{base_name}_specs.csv")
            exporter.to_excel(result, outputPath / f"{base_name}_parsed.xlsx")
            
            print(f"\n✅ Successfully parsed and exported!")
            
        except Exception as e:
            print(f"❌ Error processing {drawing_path}: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()