use dmove::{ByteArrayInterface, VarSizedAttributeElement};
use serde::Serialize;
use std::convert::TryInto;

use crate::oa_structs::Biblio;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BiblioInfo {
    volume: String,
    issue: String,
    first_page: String,
    last_page: String,
}

impl From<Biblio> for BiblioInfo {
    fn from(value: Biblio) -> Self {
        Self {
            volume: value.volume.unwrap_or("".to_string()),
            issue: value.issue.unwrap_or("".to_string()),
            first_page: value.first_page.unwrap_or("".to_string()),
            last_page: value.last_page.unwrap_or("".to_string()),
        }
    }
}

impl VarSizedAttributeElement for BiblioInfo {
    type SubType = u8;
}

impl ByteArrayInterface for BiblioInfo {
    fn to_bytes(&self) -> Box<[u8]> {
        let fields = [&self.volume, &self.issue, &self.first_page, &self.last_page];

        // --- Prefix byte ---
        // high nibble = presence bits (volume..last_page)
        // low nibble  = numeric flags (volume..last_page)
        let mut presence_bits = 0u8;
        let mut numeric_bits = 0u8;

        for (i, val) in fields.iter().enumerate() {
            if !val.is_empty() {
                presence_bits |= 1 << (3 - i);
            }
            if !val.is_empty() && val.parse::<u64>().is_ok() {
                numeric_bits |= 1 << (3 - i);
            }
        }

        let prefix = (presence_bits << 4) | numeric_bits;

        // If all missing, only prefix byte
        if presence_bits == 0 {
            return vec![prefix].into_boxed_slice();
        }

        // --- Size byte ---
        // 2 bits per attribute (volume, issue, first_page, last_page):
        // 0 => 1 byte
        // 1 => 2 bytes
        // 2 => 4 bytes
        // 3 => dynamic (1 byte length + data)
        let mut size_byte = 0u8;
        let mut field_bytes: Vec<u8> = Vec::new();

        for (i, val) in fields.iter().enumerate() {
            // if not present, skip (size bits remain 0)
            if (presence_bits & (1 << (3 - i))) == 0 {
                continue;
            }

            let is_num = (numeric_bits & (1 << (3 - i))) != 0;
            let size_code: u8;
            let bytes: Vec<u8>;

            if is_num {
                // numeric mode: choose smallest integer size that fits u8/u16/u32
                if let Ok(num) = val.parse::<u64>() {
                    if num <= u8::MAX as u64 {
                        size_code = 0; // 1 byte
                        bytes = (num as u8).to_le_bytes().to_vec();
                    } else if num <= u16::MAX as u64 {
                        size_code = 1; // 2 bytes
                        bytes = (num as u16).to_le_bytes().to_vec();
                    } else {
                        // store as u32 (4 bytes)
                        size_code = 2; // 4 bytes
                        bytes = (num as u32).to_le_bytes().to_vec();
                    }
                } else {
                    // Fallback: encode as dynamic string (shouldn't normally happen if numeric flag was correct)
                    size_code = 3; // dynamic
                    let len = val.len().min(255);
                    let mut v = Vec::with_capacity(1 + len);
                    v.push(len as u8);
                    v.extend_from_slice(&val.as_bytes()[..len]);
                    bytes = v;
                }
            } else {
                // string mode
                let len = val.len();
                if len == 1 {
                    size_code = 0; // 1 byte
                    bytes = val.as_bytes().to_vec();
                } else if len == 2 {
                    size_code = 1; // 2 bytes
                    bytes = val.as_bytes().to_vec();
                } else if len == 4 {
                    size_code = 2; // 4 bytes
                    bytes = val.as_bytes().to_vec();
                } else {
                    // dynamic
                    size_code = 3;
                    let len = len.min(255);
                    let mut v = Vec::with_capacity(1 + len);
                    v.push(len as u8);
                    v.extend_from_slice(&val.as_bytes()[..len]);
                    bytes = v;
                }
            }

            // write 2 bits for this field into size_byte
            size_byte |= (size_code & 0b11) << (6 - i * 2);

            // append bytes for this field
            field_bytes.extend(bytes);
        }

        let mut out = vec![prefix, size_byte];
        out.extend(field_bytes);
        out.into_boxed_slice()
    }

    fn from_bytes(buf: &[u8]) -> Self {
        if buf.is_empty() {
            return Self::default();
        }

        let prefix = buf[0];
        let presence_bits = prefix >> 4;
        let numeric_bits = prefix & 0x0F;

        // if nothing present
        if presence_bits == 0 {
            return Self::default();
        }

        // size byte must exist when some fields are present
        let size_byte = if buf.len() > 1 { buf[1] } else { 0 };
        let mut pos: usize = 2;
        let mut values: Vec<String> = Vec::with_capacity(4);

        for i in 0..4 {
            if (presence_bits & (1 << (3 - i))) == 0 {
                // absent
                values.push(String::new());
                continue;
            }
            let is_num = (numeric_bits & (1 << (3 - i))) != 0;
            let size_code = (size_byte >> (6 - i * 2)) & 0b11;

            let val = if is_num {
                match size_code {
                    0 => {
                        // 1 byte numeric
                        // ensure bounds
                        let v = buf.get(pos).copied().unwrap_or(0);
                        pos += 1;
                        v.to_string()
                    }
                    1 => {
                        // 2 bytes numeric (u16 little-endian)
                        let slice = &buf[pos..pos + 2];
                        let arr: [u8; 2] = slice.try_into().unwrap_or([0, 0]);
                        pos += 2;
                        u16::from_le_bytes(arr).to_string()
                    }
                    2 => {
                        // 4 bytes numeric (u32 little-endian)
                        let slice = &buf[pos..pos + 4];
                        let arr: [u8; 4] = slice.try_into().unwrap_or([0, 0, 0, 0]);
                        pos += 4;
                        u32::from_le_bytes(arr).to_string()
                    }
                    3 => {
                        // dynamic fallback for numeric: length-prefixed bytes -> interpret as utf8 string
                        let len = buf.get(pos).copied().unwrap_or(0) as usize;
                        pos += 1;
                        let slice = &buf[pos..pos + len];
                        pos += len;
                        std::str::from_utf8(slice).unwrap_or("").to_string()
                    }
                    _ => String::new(),
                }
            } else {
                match size_code {
                    0 => {
                        let slice = &buf[pos..pos + 1];
                        pos += 1;
                        std::str::from_utf8(slice).unwrap_or("").to_string()
                    }
                    1 => {
                        let slice = &buf[pos..pos + 2];
                        pos += 2;
                        std::str::from_utf8(slice).unwrap_or("").to_string()
                    }
                    2 => {
                        let slice = &buf[pos..pos + 4];
                        pos += 4;
                        std::str::from_utf8(slice).unwrap_or("").to_string()
                    }
                    3 => {
                        let len = buf.get(pos).copied().unwrap_or(0) as usize;
                        pos += 1;
                        let slice = &buf[pos..pos + len];
                        pos += len;
                        std::str::from_utf8(slice).unwrap_or("").to_string()
                    }
                    _ => String::new(),
                }
            };
            values.push(val);
        }

        Self {
            volume: values[0].clone(),
            issue: values[1].clone(),
            first_page: values[2].clone(),
            last_page: values[3].clone(),
        }
    }
}

impl Default for BiblioInfo {
    fn default() -> Self {
        Self {
            volume: "".into(),
            issue: "".into(),
            first_page: "".into(),
            last_page: "".into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_missing() {
        let info = BiblioInfo {
            volume: "".into(),
            issue: "".into(),
            first_page: "".into(),
            last_page: "".into(),
        };
        let bytes = info.to_bytes();
        assert_eq!(bytes.len(), 1);
        let decoded = BiblioInfo::from_bytes(&bytes);
        assert_eq!(info, decoded);
    }

    #[test]
    fn test_all_numeric() {
        let info = BiblioInfo {
            volume: "12".into(),
            issue: "34".into(),
            first_page: "56".into(),
            last_page: "9999".into(),
        };
        let bytes = info.to_bytes();
        let decoded = BiblioInfo::from_bytes(&bytes);
        assert_eq!(info, decoded);
    }

    #[test]
    fn test_mixed_types() {
        let info = BiblioInfo {
            volume: "A".into(),
            issue: "22".into(),
            first_page: "Page".into(),
            last_page: "".into(),
        };
        let bytes = info.to_bytes();
        let decoded = BiblioInfo::from_bytes(&bytes);
        assert_eq!(info, decoded);
    }

    #[test]
    fn test_dynamic_string() {
        let info = BiblioInfo {
            volume: "DynamicStringLongerThan4".into(),
            issue: "".into(),
            first_page: "DynamicStringLongerThan4567890".into(),
            last_page: "".into(),
        };
        let bytes = info.to_bytes();
        let decoded = BiblioInfo::from_bytes(&bytes);
        assert_eq!(info, decoded);
    }

    #[test]
    fn test_roundtrip_various() {
        let cases = vec![
            BiblioInfo {
                volume: "A".into(),
                issue: "B".into(),
                first_page: "C".into(),
                last_page: "D".into(),
            },
            BiblioInfo {
                volume: "1".into(),
                issue: "".into(),
                first_page: "99999".into(),
                last_page: "".into(),
            },
            BiblioInfo {
                volume: "".into(),
                issue: "".into(),
                first_page: "X".into(),
                last_page: "100".into(),
            },
        ];

        for info in cases {
            let bytes = info.to_bytes();
            let decoded = BiblioInfo::from_bytes(&bytes);
            assert_eq!(info, decoded, "Roundtrip failed for {:?}", info);
        }
    }
}
