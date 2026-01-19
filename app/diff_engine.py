import difflib
import re

class DiffEngine:
    @staticmethod
    def detect_new_content(old_text: str, new_text: str) -> str:
        if not old_text:
            return new_text
        
        # Normalize: remove carriage returns and trailing whitespace from the block
        old_clean = old_text.replace("\r\n", "\n").rstrip()
        new_clean = new_text.replace("\r\n", "\n").rstrip()

        if old_clean == new_clean:
            return ""

        old_lines = old_clean.splitlines()
        new_lines = new_clean.splitlines()
        
        max_possible = min(len(old_lines), len(new_lines))
        best_k = 0
        
        for k in range(max_possible, 0, -1):
             older = old_lines[-k:]
             newer = new_lines[:k]
             
             # Strict match (ignoring leading/trailing whitespace on lines to be robust)
             older_stripped = [l.strip() for l in older]
             newer_stripped = [l.strip() for l in newer]
             
             if older_stripped == newer_stripped:
                 best_k = k
                 break
                 
             # Fuzzy match
             match_count = 0
             for o_line, n_line in zip(older_stripped, newer_stripped):
                 if o_line == n_line:
                     match_count += 1
                     continue
                 
                 ratio = difflib.SequenceMatcher(None, o_line, n_line).ratio()
                 if ratio > 0.9:
                     match_count += 1
            
             if match_count == k:
                 best_k = k
                 break

        if best_k > 0:
             diff_lines = new_lines[best_k:]
             return DiffEngine._filter_and_join(diff_lines)

        # Fallback: Robust Subset/Jitter Check using Opcodes
        # Use simple normalized text for this check to avoid line-splitting artifacts
        if DiffEngine._is_mostly_subset_or_jitter(old_clean, new_clean):
            return ""

        return DiffEngine._filter_and_join(new_lines)

    @staticmethod
    def _is_mostly_subset_or_jitter(old: str, new: str) -> bool:
        s = difflib.SequenceMatcher(None, old, new)
        opcodes = s.get_opcodes()
        
        new_insertion_len = 0
        total_new_len = len(new)
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'insert':
                new_insertion_len += (j2 - j1)
            elif tag == 'replace':
                old_block = old[i1:i2]
                new_block = new[j1:j2]
                
                # Check for substring (indicates misalignment/loss rather than new info)
                if new_block in old_block:
                    continue
                
                # Fuzzy Check
                if len(new_block) > 5:
                    sm = difflib.SequenceMatcher(None, old_block, new_block)
                    if sm.find_longest_match(0, len(old_block), 0, len(new_block)).size / len(new_block) > 0.8:
                        continue
                
                new_insertion_len += (j2 - j1)
        
        if total_new_len == 0:
            return True
            
        # If new content is less than 15% of total, treat as jitter/subset
        return (new_insertion_len / total_new_len) < 0.15

        return DiffEngine._filter_and_join(new_lines)

    @staticmethod
    def _filter_and_join(lines: list[str]) -> str:
        filtered = []
        pattern = re.compile(r".+ Lv\. \d{1,2}:\d{2}:\d{2}")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if pattern.search(line):
                continue
            filtered.append(line)
        return "\n".join(filtered)
