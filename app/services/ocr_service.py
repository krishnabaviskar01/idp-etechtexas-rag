"""
OCR service for text extraction, chunking, and language detection
"""
import io
import os
import unicodedata
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langdetect import detect, detect_langs, LangDetectException
from slugify import slugify
from loguru import logger
import regex


class OCRService:
    """Service for OCR text extraction, chunking, and language detection"""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        """
        Initialize OCR service
        
        Args:
            chunk_size: Chunk size in characters (default: 512)
            chunk_overlap: Chunk overlap in characters (default: 50)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize LangChain text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                ". ",    # Sentence endings
                "? ",
                "! ",
                " ",     # Spaces
            ]
        )
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text: collapse extra spaces, preserve paragraph breaks, NFC Unicode
        
        Args:
            text: Raw text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Normalize Unicode to NFC
        text = unicodedata.normalize('NFC', text)
        
        # Preserve paragraph breaks (double newlines)
        # Replace multiple spaces with single space (but preserve \n\n)
        text = regex.sub(r'[ \t]+', ' ', text)  # Collapse spaces/tabs
        text = regex.sub(r'\n[ \t]+', '\n', text)  # Remove spaces after newlines
        text = regex.sub(r'[ \t]+\n', '\n', text)  # Remove spaces before newlines
        
        # Collapse multiple newlines (but preserve at least one)
        text = regex.sub(r'\n{3,}', '\n\n', text)
        
        # Trim whitespace
        text = text.strip()
        
        return text
    
    def extract_pdf_text(self, file_bytes: bytes, file_name: str) -> Tuple[str, int, int]:
        """
        Extract text from PDF using PyMuPDF
        
        Args:
            file_bytes: PDF file content as bytes
            file_name: File name for logging
            
        Returns:
            Tuple of (text, total_pages, pages_without_text)
        """
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            pages_without_text = 0
            text_parts = []
            
            logger.info(f"Processing PDF: {file_name} ({total_pages} pages)")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # Try blocks first (better reading order)
                try:
                    blocks = page.get_text("blocks")
                    page_text = ""
                    for block in blocks:
                        if len(block) >= 4:  # Block has text content
                            block_text = block[4]
                            if block_text:
                                page_text += block_text + "\n"
                    
                    if not page_text.strip():
                        # Fallback to regular text extraction
                        page_text = page.get_text("text")
                except Exception:
                    # Fallback to regular text extraction
                    page_text = page.get_text("text")
                
                page_text = self.normalize_text(page_text)
                
                if not page_text.strip():
                    pages_without_text += 1
                    logger.warning(
                        f"Page {page_num + 1} in {file_name} has no extractable text "
                        "(image-only page)"
                    )
                else:
                    text_parts.append(page_text)
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            
            logger.info(
                f"Extracted text from PDF: {file_name} "
                f"({total_pages} pages, {pages_without_text} without text)"
            )
            
            return full_text, total_pages, pages_without_text
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_name}: {e}")
            raise
    
    def extract_docx_text(self, file_bytes: bytes, file_name: str) -> Tuple[str, int, int]:
        """
        Extract text from DOC/DOCX using python-docx
        
        Args:
            file_bytes: DOCX file content as bytes
            file_name: File name for logging
            
        Returns:
            Tuple of (text, total_pages (always 1), pages_without_text (always 0))
        """
        try:
            doc = Document(io.BytesIO(file_bytes))
            paragraphs = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
            
            text = "\n\n".join(paragraphs)
            text = self.normalize_text(text)
            
            logger.info(f"Extracted text from DOCX: {file_name}")
            
            # DOC/DOCX treated as single page
            return text, 1, 0
        
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {file_name}: {e}")
            raise
    
    def extract_txt_text(self, file_bytes: bytes, file_name: str) -> Tuple[str, int, int]:
        """
        Extract text from TXT file
        
        Args:
            file_bytes: TXT file content as bytes
            file_name: File name for logging
            
        Returns:
            Tuple of (text, total_pages (always 1), pages_without_text (always 0))
        """
        try:
            # Try UTF-8 first
            try:
                text = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Fallback to latin-1
                text = file_bytes.decode('latin-1')
            
            text = self.normalize_text(text)
            
            logger.info(f"Extracted text from TXT: {file_name}")
            
            # TXT treated as single page
            return text, 1, 0
        
        except Exception as e:
            logger.error(f"Error extracting text from TXT {file_name}: {e}")
            raise
    
    def extract_text(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: Optional[str] = None
    ) -> Tuple[str, int, int]:
        """
        Extract text from file based on extension/MIME type
        
        Args:
            file_bytes: File content as bytes
            file_name: File name
            mime_type: Optional MIME type
            
        Returns:
            Tuple of (text, total_pages, pages_without_text)
        """
        ext = os.path.splitext(file_name)[1].lower()
        
        if ext == '.pdf' or mime_type == 'application/pdf':
            return self.extract_pdf_text(file_bytes, file_name)
        elif ext in ['.doc', '.docx'] or mime_type in [
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]:
            return self.extract_docx_text(file_bytes, file_name)
        elif ext == '.txt' or mime_type == 'text/plain':
            return self.extract_txt_text(file_bytes, file_name)
        else:
            raise ValueError(f"Unsupported file type: {file_name} (ext: {ext}, mime: {mime_type})")
    
    def detect_language(self, text: str) -> str:
        """
        Detect language of text using langdetect
        
        Args:
            text: Text to detect language for
            
        Returns:
            Language code (2-letter ISO code) or "und" if undetected
        """
        if not text or not text.strip():
            return "und"
        
        try:
            # Try simple detection
            lang = detect(text)
            
            # Validate format (should be 2-letter code)
            if re.match(r'^[a-z]{2}$', lang):
                return lang
            else:
                logger.warning(f"Detected language '{lang}' doesn't match expected format")
                return "und"
        
        except LangDetectException:
            try:
                # Try detect_langs and pick top with prob >= 0.75
                langs = detect_langs(text)
                if langs and len(langs) > 0:
                    top_lang = langs[0]
                    if top_lang.prob >= 0.75:
                        lang_code = top_lang.lang
                        if re.match(r'^[a-z]{2}$', lang_code):
                            return lang_code
                
                logger.warning(f"Could not detect language with confidence >= 0.75")
                return "und"
            
            except Exception as e:
                logger.warning(f"Language detection failed: {e}")
                return "und"
    
    def chunk_text(
        self,
        text: str,
        page_index: int,
        total_pages: int
    ) -> List[Dict[str, Any]]:
        """
        Chunk text using LangChain RecursiveCharacterTextSplitter
        
        Args:
            text: Text to chunk
            page_index: Page index (0-based)
            total_pages: Total number of pages
            
        Returns:
            List of chunk dictionaries
        """
        if not text or not text.strip():
            return []
        
        # Split text into chunks
        chunks = self.text_splitter.split_text(text)
        
        # Filter out empty chunks
        valid_chunks = []
        for idx, chunk_text in enumerate(chunks):
            chunk_text = chunk_text.strip()
            
            if not chunk_text:
                continue
            
            valid_chunks.append({
                'chunk_index': idx,
                'text': chunk_text
            })
        
        logger.debug(
            f"Created {len(valid_chunks)} chunks from page {page_index + 1} "
            f"(avg size: {sum(len(c['text']) for c in valid_chunks) / len(valid_chunks) if valid_chunks else 0:.0f} chars)"
        )
        
        return valid_chunks
    
    def process_document(
        self,
        file_bytes: bytes,
        file_name: str,
        doc_id: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a document: extract text, detect language, chunk
        
        Args:
            file_bytes: File content as bytes
            file_name: File name
            doc_id: Optional document ID (will be generated if not provided)
            mime_type: Optional MIME type
            
        Returns:
            Dictionary with processed document data
        """
        # Generate doc_id if not provided
        if not doc_id:
            basename = os.path.splitext(file_name)[0]
            slug = slugify(basename)
            from datetime import datetime
            date_str = datetime.now().strftime('%Y-%m-%d')
            doc_id = f"doc:{slug}@{date_str}"
        
        # Extract text
        text, total_pages, pages_without_text = self.extract_text(
            file_bytes, file_name, mime_type
        )
        
        if not text or not text.strip():
            logger.warning(f"Document {file_name} has no extractable text")
            return {
                'doc_id': doc_id,
                'file_name': file_name,
                'language': 'und',
                'total_page_count': total_pages,
                'pages_without_text': pages_without_text,
                'chunks': [],
                'chunks_emitted': 0,
                'lang_undetected': False
            }
        
        # Detect language
        language = self.detect_language(text)
        lang_undetected = (language == "und")
        
        if lang_undetected:
            logger.warning(f"Could not detect language for {file_name}")
        
        # Chunk text
        # For PDFs: chunk per page; for DOC/DOCX/TXT: single page
        all_chunks = []
        
        if total_pages == 1:
            # Single page document (DOC/DOCX/TXT or single-page PDF)
            page_chunks = self.chunk_text(text, 0, 1)
            for chunk in page_chunks:
                all_chunks.append({
                    'doc_id': doc_id,
                    'file_name': file_name,
                    'language': language,
                    'total_page_count': total_pages,
                    'page_index': 0,
                    'chunk_index': chunk['chunk_index'],
                    'text': chunk['text']
                })
        else:
            # Multi-page PDF: chunk per page
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # Extract page text
                try:
                    blocks = page.get_text("blocks")
                    page_text = ""
                    for block in blocks:
                        if len(block) >= 4:
                            block_text = block[4]
                            if block_text:
                                page_text += block_text + "\n"
                    if not page_text.strip():
                        page_text = page.get_text("text")
                except Exception:
                    page_text = page.get_text("text")
                
                page_text = self.normalize_text(page_text)
                
                if page_text.strip():
                    page_chunks = self.chunk_text(page_text, page_num, total_pages)
                    for chunk in page_chunks:
                        all_chunks.append({
                            'doc_id': doc_id,
                            'file_name': file_name,
                            'language': language,
                            'total_page_count': total_pages,
                            'page_index': page_num,
                            'chunk_index': chunk['chunk_index'],
                            'text': chunk['text']
                        })
            
            doc.close()
        
        logger.info(
            f"Processed document {file_name}: {len(all_chunks)} chunks, "
            f"language={language}, pages={total_pages}"
        )
        
        return {
            'doc_id': doc_id,
            'file_name': file_name,
            'language': language,
            'total_page_count': total_pages,
            'pages_without_text': pages_without_text,
            'chunks': all_chunks,
            'chunks_emitted': len(all_chunks),
            'lang_undetected': lang_undetected
        }

