#!/usr/bin/python3
import csv
from datetime import datetime
import time
import os
import re
import sys
import logging
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd7in5_V2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quote_display.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class EinkQuoteDisplay:
    def __init__(self):
        try:
            logging.info("Initializing E-ink display")
            # Initialize the e-ink display
            self.epd = epd7in5_V2.EPD()
            self.epd.init()
            
            # Get the display dimensions
            self.width = self.epd.width
            self.height = self.epd.height
            
            # Load fonts
            self.font_path = "/usr/share/fonts/truetype/times/"
            self.update_fonts(24)  # Initial size of 24
            
            # Load quotes and create initial image
            self.quotes = self.load_quotes()
            if not self.quotes:
                raise Exception("No quotes loaded from CSV file")
            
            self.last_time = None
            self.create_new_image()
            logging.info("Initialization complete")
        except Exception as e:
            logging.error(f"Initialization failed: {str(e)}")
            raise
    
    def update_fonts(self, size):
        """Update font objects with new size"""
        try:
            self.font_regular = ImageFont.truetype(os.path.join(self.font_path, "times.ttf"), size)
            self.font_bold = ImageFont.truetype(os.path.join(self.font_path, "timesbd.ttf"), size)
            self.font_italic = ImageFont.truetype(os.path.join(self.font_path, "timesi.ttf"), size - 4)
        except Exception as e:
            logging.error(f"Font loading failed: {str(e)}")
            raise

    def load_quotes(self):
        """Load quotes from CSV file"""
        quotes = {}
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, 'quotes.csv')
            logging.info(f"Loading quotes from {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                headers = next(reader)
                
                for row in reader:
                    if len(row) >= 5:
                        time_key = row[0].strip()
                        quotes[time_key] = {
                            'to_bold': row[1].strip(),
                            'quote': row[2].strip(),
                            'book': row[3].strip(),
                            'author': row[4].strip()
                        }
            
            logging.info(f"Loaded {len(quotes)} quotes")
            return quotes
        except Exception as e:
            logging.error(f"Error loading quotes: {str(e)}")
            raise

    def calculate_font_size(self, text):
        """Calculate appropriate font size based on text length"""
        length = len(text)
        if length < 100:
            return 32
        elif length < 200:
            return 28
        elif length < 300:
            return 24
        else:
            return 20

    def process_line_breaks(self, text):
        """Process any HTML-style line breaks in text"""
        return re.sub(r'<[^>]*>', '\n', text)

    def create_new_image(self):
        """Create a new blank image for the display"""
        self.image = Image.new('1', (self.width, self.height), 255)
        self.draw = ImageDraw.Draw(self.image)

    def wrap_text(self, text, font, max_width):
        """Wrap text to fit within specified width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            line_width, _ = font.getsize(' '.join(current_line))
            if line_width > max_width:
                if len(current_line) == 1:
                    lines.append(current_line[0])
                    current_line = []
                else:
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        return lines

    def display_quote(self, quote_data):
        """Display a quote on the e-ink display"""
        try:
            self.create_new_image()
            
            # Process the quote text
            quote = self.process_line_breaks(quote_data['quote'])
            to_bold = quote_data['to_bold']
            
            # Calculate font size based on quote length
            font_size = self.calculate_font_size(quote)
            self.update_fonts(font_size)
            
            # Wrap text to fit display width
            margin = 40
            max_width = self.width - (2 * margin)
            
            # Split quote into parts: before bold, bold, and after bold
            if to_bold and to_bold in quote:
                parts = quote.split(to_bold)
                before_text = parts[0]
                after_text = parts[1] if len(parts) > 1 else ""
                
                # Calculate positions and draw text
                y_position = margin
                
                # Draw before text
                before_lines = self.wrap_text(before_text.strip(), self.font_regular, max_width)
                for line in before_lines:
                    self.draw.text((margin, y_position), line, font=self.font_regular, fill=0)
                    y_position += font_size + 5
                
                # Draw bold text
                bold_lines = self.wrap_text(to_bold.strip(), self.font_bold, max_width)
                for line in bold_lines:
                    self.draw.text((margin, y_position), line, font=self.font_bold, fill=0)
                    y_position += font_size + 5
                
                # Draw after text
                after_lines = self.wrap_text(after_text.strip(), self.font_regular, max_width)
                for line in after_lines:
                    self.draw.text((margin, y_position), line, font=self.font_regular, fill=0)
                    y_position += font_size + 5
            else:
                # Draw regular text without bold
                y_position = margin
                lines = self.wrap_text(quote.strip(), self.font_regular, max_width)
                for line in lines:
                    self.draw.text((margin, y_position), line, font=self.font_regular, fill=0)
                    y_position += font_size + 5
            
            # Draw attribution
            attribution = f"- {quote_data['book']} by {quote_data['author']}"
            self.draw.text((margin, self.height - 60), attribution, font=self.font_italic, fill=0)
            
            # Update the display
            self.epd.display(self.epd.getbuffer(self.image))
            logging.info(f"Successfully displayed quote from {quote_data['book']}")
        except Exception as e:
            logging.error(f"Error displaying quote: {str(e)}")
            raise

    def cleanup(self):
        """Clean up the display on exit"""
        try:
            logging.info("Cleaning up display")
            self.epd.init()
            self.epd.Clear()
            self.epd.sleep()
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

    def update_display(self):
        """Main loop to update the display"""
        try:
            while True:
                current_time = datetime.now().strftime("%H:%M")
                
                # Only update if the time has changed
                if current_time != self.last_time:
                    logging.info(f"Time changed to {current_time}, updating display")
                    quote_data = self.quotes.get(current_time)
                    
                    if not quote_data:
                        quote_data = self.quotes.get("0:00 midnight")
                    
                    if quote_data:
                        self.display_quote(quote_data)
                        self.last_time = current_time
                    else:
                        logging.warning(f"No quote found for time {current_time}")
                
                # Sleep for 30 seconds before checking again
                time.sleep(30)
                
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, shutting down")
            self.cleanup()
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
            self.cleanup()
            raise

def main():
    try:
        logging.info("Starting E-ink Quote Display")
        display = EinkQuoteDisplay()
        display.update_display()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()