"""
UE4/UE5 Localization Resource (.locres) binary format tools.

Provides hash functions and binary read/write for Unreal Engine localization files.
Extracted and generalized from the WOJD translation pipeline.
"""

import struct
import zlib

try:
    import cityhash
except ImportError:
    cityhash = None

from .utils import normalize_line_endings_for_hash, clean_key_bom


# --- LocRes Constants ---
LOCRES_MAGIC_BYTES = bytes([
    0x0E, 0x14, 0x74, 0x75, 0x67, 0x4A, 0x03, 0xFC,
    0x4A, 0x15, 0x90, 0x9D, 0xC3, 0x37, 0x7F, 0x1B
])
LOCRES_VERSION_OPTIMIZED_CITYHASH_UTF16 = 0x03  # UE4 standard
# LOCRES_VERSION_UE5 = 0x04  # Reserved for UE5 support


# --- Hash Functions ---

def calculate_cityhash64_key_hash(key_string):
    """
    Calculate the UE4 optimized CityHash64 key hash for a namespace or key string.

    The hash is computed on UTF-16LE encoded text with normalized line endings,
    then folded from 64-bit to 32-bit using UE4's specific formula.

    Args:
        key_string: The namespace or key string to hash.

    Returns:
        32-bit unsigned integer hash value.
    """
    if not cityhash:
        raise ImportError("cityhash library is required. Install with: pip install cityhash")
    if not isinstance(key_string, str):
        raise TypeError("Input must be a string.")

    normalized = normalize_line_endings_for_hash(key_string)
    encoded = normalized.encode('utf-16-le')
    h64 = cityhash.CityHash64(encoded)
    low32 = h64 & 0xFFFFFFFF
    high32 = (h64 >> 32) & 0xFFFFFFFF
    return (low32 + (high32 * 23)) & 0xFFFFFFFF


def calculate_source_string_hash(text):
    """
    Calculate the UE4 source string hash (CRC32 of UTF-16LE with 2-byte padding per char).

    This matches UE4's internal hashing for source strings in .locres files.

    Args:
        text: The source text to hash.

    Returns:
        32-bit unsigned integer CRC32 hash value.
    """
    encoded = text.encode('utf-16-le')
    # Insert 2 null bytes after every 2-byte UTF-16LE code unit
    padded = b''.join(encoded[i:i+2] + b'\x00\x00' for i in range(0, len(encoded), 2))
    return zlib.crc32(padded) & 0xFFFFFFFF


# --- Binary Write Helpers ---

def write_fstring(stream, text):
    """
    Write an FString to a binary stream in UE4 locres format.

    Strings are written as UTF-16LE with a negative length prefix (indicating UTF-16).

    Args:
        stream: Binary file stream to write to.
        text: String to write (None is treated as empty string).
    """
    if text is None:
        text = ""
    text_with_null = text + '\0'
    try:
        encoded = text_with_null.encode('utf-16-le')
        num_chars = len(encoded) // 2  # including null terminator
        stream.write(struct.pack('<i', -num_chars))  # negative = UTF-16
        stream.write(encoded)
    except Exception as e:
        print(f"ERROR encoding string to UTF-16LE: '{text[:50]}...' ({e}). Writing empty.")
        stream.write(struct.pack('<i', -1))
        stream.write(b'\x00\x00')


# --- LocRes File Generation ---

def generate_locres_file(all_namespace_data, output_path, version=LOCRES_VERSION_OPTIMIZED_CITYHASH_UTF16):
    """
    Generate a .locres binary file from structured namespace data.

    Args:
        all_namespace_data: List of namespace dicts, each containing:
            - namespace_name (str): The namespace name
            - namespace_hash (int): Pre-computed CityHash64 of namespace
            - entries (list): List of entry dicts with:
                - key_string (str): The key
                - key_hash (int): Pre-computed CityHash64 of key
                - source_string_hash (int): CRC32 of source text
                - translated_value (str): The translated string
        output_path: Path to write the .locres file.
        version: LocRes format version (default: 0x03 for UE4).
    """
    import os
    print(f"  Generating .locres (v{version:#04x}): {output_path}")
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            # Header
            f.write(LOCRES_MAGIC_BYTES)
            f.write(struct.pack('<B', version))

            # Placeholder for string table offset
            string_table_offset_pos = f.tell()
            f.write(struct.pack('<q', 0))

            # Entry counts
            total_entries = sum(len(ns.get("entries", [])) for ns in all_namespace_data)
            f.write(struct.pack('<i', total_entries))
            f.write(struct.pack('<i', len(all_namespace_data)))

            # Build deduplicated string table
            string_to_index = {}
            string_table = []
            for ns_data in all_namespace_data:
                for entry in ns_data.get("entries", []):
                    val = entry["translated_value"]
                    if val not in string_to_index:
                        idx = len(string_table)
                        string_table.append(val)
                        string_to_index[val] = {"index": idx, "ref_count": 1}
                    else:
                        string_to_index[val]["ref_count"] += 1

            # Write namespace entries
            for ns_data in all_namespace_data:
                f.write(struct.pack('<I', ns_data["namespace_hash"]))
                write_fstring(f, ns_data["namespace_name"])
                f.write(struct.pack('<i', len(ns_data.get("entries", []))))
                for entry in ns_data.get("entries", []):
                    f.write(struct.pack('<I', entry["key_hash"]))
                    write_fstring(f, entry["key_string"])
                    f.write(struct.pack('<I', entry["source_string_hash"]))
                    f.write(struct.pack('<i', string_to_index[entry["translated_value"]]["index"]))

            # Write string table at current position
            actual_offset = f.tell()
            f.seek(string_table_offset_pos)
            f.write(struct.pack('<q', actual_offset))
            f.seek(actual_offset)

            f.write(struct.pack('<i', len(string_table)))
            for val in string_table:
                write_fstring(f, val)
                f.write(struct.pack('<i', string_to_index[val]["ref_count"]))

            print(f"    Generated .locres: {total_entries} entries, {len(string_table)} unique strings")
    except Exception as e:
        print(f"    ERROR generating .locres at {output_path}: {e}")
        import traceback
        traceback.print_exc()


# --- CSV Loading ---

def load_locres_hash_csv(csv_path):
    """
    Load a unified locres hash CSV file.

    Returns:
        Tuple of (data_map, namespace_info) where:
        - data_map: dict keyed by (namespace, key) with hash data
        - namespace_info: dict of namespace -> {hash, order}
        Returns (None, None) on error.
    """
    import csv

    data_map = {}
    namespace_info = {}
    ns_order = 0

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            required = ['Namespace', 'Key', 'SourceValue', 'NamespaceHash',
                        'KeyHash_of_KeyString', 'SourceStringHash_of_SourceText']
            if not reader.fieldnames or not all(h in reader.fieldnames for h in required):
                print(f"ERROR: CSV missing required columns. Found: {reader.fieldnames}")
                return None, None

            for row in reader:
                ns = clean_key_bom(row['Namespace'])
                key = clean_key_bom(row['Key'])
                if ns not in namespace_info:
                    namespace_info[ns] = {"hash": int(row['NamespaceHash']), "order": ns_order}
                    ns_order += 1
                data_map[(ns, key)] = {
                    'namespace_name': ns,
                    'key_string': key,
                    'namespace_hash': namespace_info[ns]["hash"],
                    'key_hash': int(row['KeyHash_of_KeyString']),
                    'source_value': row['SourceValue'],
                    'source_string_hash': int(row['SourceStringHash_of_SourceText'])
                }

        print(f"  Loaded {len(data_map)} entries from '{csv_path}'")
        return data_map, namespace_info
    except FileNotFoundError:
        print(f"ERROR: CSV not found: {csv_path}")
        return None, None
    except Exception as e:
        print(f"ERROR: Failed to parse CSV '{csv_path}': {e}")
        return None, None
