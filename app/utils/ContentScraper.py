import requests
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import fitz
from selenium import webdriver

class ContentScraper:
    def __init__(self, url):
        self.soup = self.initiate_soup(url)
        self.url = url
        self.visited_links = set()

    def initiate_soup(self, url):
        initial_content = self.get_initial_content(url)
        if self.needs_selenium(initial_content):
            return self.get_soup_with_selenium(url)
        return BeautifulSoup(initial_content, 'lxml')

    def get_initial_content(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
                }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error fetching initial site content: {e}")
            return None
    
    def needs_selenium(self, content):
        if content is None:
            return True  # Fallback to Selenium if initial fetch fails
        soup_text = re.sub(r'\s+', ' ', BeautifulSoup(content, 'lxml').get_text()).strip()
        # Heuristic: Check for insufficient content
        if len(soup_text) < 100:
            return True
        return False
    
    def get_soup_with_selenium(self, url):
        try:
            # Setup options for headless browsing
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            # Initialize the driver (ensure that you have the chromedriver that matches your Chrome version)
            driver = webdriver.Chrome(options=options) 
            driver.get(url)
            # You may need to wait here for certain elements to load
            page_source = driver.page_source
            driver.quit()
            return BeautifulSoup(page_source, 'lxml')
        except Exception as e:
            print(f"Error scraping site with Selenium: {e}")
            return None

    def extract_static_content(self):
        if self.soup is None:
            return ""
        
        main_content = self.find_main_content_area()
        if not main_content:
            return ""

        current_section = None
        all_content_str = ""  # For final single string output
        encountered_content = set()  # Track encountered content to avoid duplicates

        # Process content-specific tags
        for tag in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'textarea', 'pre']):
            if self.should_skip_tag(tag):
                continue

            tag_content_hash = self.generate_content_hash(tag)
            if tag_content_hash in encountered_content:
                continue
            encountered_content.add(tag_content_hash)

            full_text = self.process_tag_text(tag)
            if full_text:
                current_section, all_content_str = self.update_content_structure(tag, full_text, current_section, all_content_str)
        
        return all_content_str

    def extract_links(self):
        """Extracts and returns a set of internal links from the given BeautifulSoup object, excluding
        external links, email links, telephone links, and anchor links."""
        
        links = set()
        for link in self.soup.find_all('a', href=True):
            href = link['href'].strip()

            # Skip empty links
            if href == "":
                continue

            # Exclude links that start with 'mailto:', 'tel:', or contain '#'
            if href.startswith('mailto:') or href.startswith('tel:') or '#' in href:
                continue

            # Complete relative links (if any)
            href = urljoin(self.url, href)

            # Extract base URL to compare and identify external links
            link_base = urlparse(href).netloc
            site_base = urlparse(self.url).netloc

            # Check if the extracted link is an internal link
            if link_base == site_base and href not in self.visited_links:
                links.add(href)

        return links
    
    def find_main_content_area(self):
        main_content_selectors = ['main', 'article', 'div#content', 'div.content']
        for selector in main_content_selectors:
            main_content = self.soup.select_one(selector)
            if main_content:
                return main_content
        return self.soup  # Fallback to entire soup if no main content detected

    def should_skip_tag(self, tag):
        
        return any(keyword in ' '.join(tag.get('class', [])) + tag.get('id', '') for keyword in ['nav', 'footer', 'sidebar'])

    def generate_content_hash(self, tag):
        
        return hash((tag.name, tag.get_text(separator=' ', strip=True), str(tag.attrs)))

    def process_tag_text(self, tag):
        text = tag.get_text(separator=' ', strip=True)
        href = tag.get('href', '')
        return f'{text} {href}'.strip() if href else text

    def update_content_structure(self, tag, full_text, current_section, all_content_str):
        # Enhanced content structuring
        if tag.name.startswith('h') and tag.name[1:].isdigit():
            current_section = {'title': full_text, 'content': []}
            all_content_str += "\n\n" + full_text + "\n"
        else:
            if current_section is None:
                current_section = {'title': 'General', 'content': []}
            current_section['content'].append(full_text)
            all_content_str += full_text + " "
        return current_section, all_content_str

    def extract_content(self):
        # The initiate_soup method already decides whether to use Selenium based on the initial content.
        # So, we directly call it to initialize self.soup.
        self.soup = self.initiate_soup(self.url)
        
        # After initializing self.soup, you can proceed with extracting the content.
        # The dynamic_content flag can be set based on whether Selenium was used.
        # This requires a slight modification to return a flag from initiate_soup indicating the method used.
        return self.extract_static_content()

    @staticmethod
    def extract_text_from_pdf(file):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
