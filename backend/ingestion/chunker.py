import re
from typing import List, Dict, Any


class CodeChunker:
    """
    AST-aware code chunker that splits files into semantically meaningful pieces.
    Falls back to line-based chunking for unsupported languages.
    """

    MAX_CHUNK_SIZE = 1500  # characters
    OVERLAP = 100

    def chunk(self, content: str, file_path: str, language: str) -> List[Dict[str, Any]]:
        if language in ("Python",):
            return self._chunk_python(content, file_path)
        elif language in ("JavaScript", "TypeScript"):
            return self._chunk_js_ts(content, file_path)
        elif language == "Java":
            return self._chunk_java(content, file_path)
        else:
            return self._chunk_generic(content, file_path, language)

    def _chunk_python(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        chunks = []
        lines = content.split("\n")
        current_chunk: List[str] = []
        current_start = 0
        current_name = None
        current_type = "module"

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Detect function/class definitions
            is_def = stripped.startswith("def ") or stripped.startswith("async def ")
            is_class = stripped.startswith("class ")

            if (is_def or is_class) and current_chunk:
                # Save previous chunk
                chunks.append(self._make_chunk(
                    "\n".join(current_chunk), file_path, current_type,
                    current_name, current_start, i - 1
                ))
                current_chunk = []
                current_start = i
                current_name = self._extract_name(stripped)
                current_type = "function" if is_def else "class"

            current_chunk.append(line)

            # Flush large chunks
            if len("\n".join(current_chunk)) > self.MAX_CHUNK_SIZE:
                chunks.append(self._make_chunk(
                    "\n".join(current_chunk), file_path, current_type,
                    current_name, current_start, i
                ))
                current_chunk = current_chunk[-5:]  # small overlap
                current_start = i - 5

            i += 1

        if current_chunk:
            chunks.append(self._make_chunk(
                "\n".join(current_chunk), file_path, current_type,
                current_name, current_start, len(lines) - 1
            ))

        return [c for c in chunks if c["content"].strip()]

    def _chunk_js_ts(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk JS/TS by function/class boundaries."""
        # Regex-based function/class detection
        pattern = re.compile(
            r"(export\s+)?(default\s+)?(async\s+)?function\s+(\w+)|"
            r"(export\s+)?(default\s+)?class\s+(\w+)|"
            r"const\s+(\w+)\s*=\s*(async\s*)?\(|"
            r"const\s+(\w+)\s*=\s*(async\s*)?function"
        )
        return self._regex_chunk(content, file_path, pattern, "JavaScript/TypeScript")

    def _chunk_java(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        pattern = re.compile(
            r"(public|private|protected)?\s*(static)?\s*\w+\s+(\w+)\s*\("
        )
        return self._regex_chunk(content, file_path, pattern, "Java")

    def _regex_chunk(self, content: str, file_path: str, pattern, language: str) -> List[Dict[str, Any]]:
        chunks = []
        lines = content.split("\n")
        boundaries = [0]

        for i, line in enumerate(lines):
            if pattern.search(line):
                boundaries.append(i)

        boundaries.append(len(lines))

        for idx in range(len(boundaries) - 1):
            start = boundaries[idx]
            end = boundaries[idx + 1]
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines)

            if len(chunk_content) > self.MAX_CHUNK_SIZE:
                # Sub-chunk large blocks
                sub_chunks = self._split_by_size(chunk_content, file_path, start)
                chunks.extend(sub_chunks)
            elif chunk_content.strip():
                name = self._extract_name(lines[start].strip()) if chunk_lines else None
                chunks.append(self._make_chunk(chunk_content, file_path, "function", name, start, end - 1))

        return chunks

    def _chunk_generic(self, content: str, file_path: str, language: str) -> List[Dict[str, Any]]:
        """Sliding window chunking for unsupported languages."""
        chunks = []
        lines = content.split("\n")
        window = 60
        step = 50

        for i in range(0, len(lines), step):
            chunk_lines = lines[i:i + window]
            chunk_content = "\n".join(chunk_lines)
            if chunk_content.strip():
                chunks.append(self._make_chunk(chunk_content, file_path, "block", None, i, i + len(chunk_lines) - 1))

        return chunks

    def _split_by_size(self, content: str, file_path: str, start_offset: int) -> List[Dict[str, Any]]:
        lines = content.split("\n")
        chunks = []
        current = []
        current_start = start_offset

        for i, line in enumerate(lines):
            current.append(line)
            if len("\n".join(current)) > self.MAX_CHUNK_SIZE:
                chunks.append(self._make_chunk(
                    "\n".join(current), file_path, "block", None,
                    current_start, current_start + len(current) - 1
                ))
                current = current[-5:]
                current_start = start_offset + i - 5

        if current:
            chunks.append(self._make_chunk(
                "\n".join(current), file_path, "block", None,
                current_start, current_start + len(current) - 1
            ))

        return chunks

    @staticmethod
    def _make_chunk(content: str, file_path: str, chunk_type: str,
                    name: str, start_line: int, end_line: int) -> Dict[str, Any]:
        return {
            "content": content,
            "file_path": file_path,
            "type": chunk_type,
            "name": name,
            "start_line": start_line,
            "end_line": end_line,
        }

    @staticmethod
    def _extract_name(line: str) -> str:
        match = re.search(r"(?:def|class|function|const|async def)\s+(\w+)", line)
        return match.group(1) if match else None
