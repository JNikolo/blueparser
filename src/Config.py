from dotenv import load_dotenv
import os

class Config:
    """Centralized configuration loader."""

    def __init__(self):
        # Load environment variables once
        load_dotenv()

        # AWS credentials
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        # S3 bucket for Textract async operations (required for multi-page PDFs)
        self.AWS_TEXTRACT_S3_BUCKET = os.getenv("AWS_TEXTRACT_S3_BUCKET")

        # CORS configuration
        self.ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    def as_dict(self):
        return {
            "AWS_ACCESS_KEY_ID": self.AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": self.AWS_SECRET_ACCESS_KEY,
            "AWS_DEFAULT_REGION": self.AWS_DEFAULT_REGION,
            "AWS_TEXTRACT_S3_BUCKET": self.AWS_TEXTRACT_S3_BUCKET,
            "ALLOWED_ORIGINS": self.ALLOWED_ORIGINS,
        }

# Create a singleton instance so it's only loaded once
config = Config()