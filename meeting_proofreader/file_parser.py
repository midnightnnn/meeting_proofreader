"""
파일 파서 모듈
TXT, HWP 파일에서 텍스트 추출
"""
import io
from pathlib import Path


def extract_text_from_file(file_data: bytes, filename: str) -> str:
    """파일에서 텍스트 추출. 지원 형식: TXT, HWP"""
    ext = Path(filename).suffix.lower()
    
    if ext == '.txt':
        return _extract_txt(file_data)
    elif ext == '.hwp':
        return _extract_hwp(file_data)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")


def _extract_txt(data: bytes) -> str:
    """TXT 파일 텍스트 추출 (인코딩 자동 감지)"""
    encodings = ["utf-8", "euc-kr", "cp949", "utf-16"]
    for enc in encodings:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 인식할 수 없습니다.")


def _extract_hwp(data: bytes) -> str:
    """HWP 파일 텍스트 추출 (레코드 구조 파싱)"""
    import struct
    
    try:
        import olefile
    except ImportError:
        raise ImportError("HWP 지원을 위해 olefile을 설치하세요: pip install olefile")
    
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
        dirs = ole.listdir()
        
        # HWP 파일 검증
        if ["FileHeader"] not in dirs:
            raise ValueError("유효하지 않은 HWP 파일입니다.")
        
        # 문서 포맷 압축 여부 확인
        header = ole.openstream("FileHeader")
        header_data = header.read()
        is_compressed = (header_data[36] & 1) == 1
        
        # Body Sections 수집 (Section0, Section1, ...)
        section_nums = []
        for d in dirs:
            if d[0] == "BodyText":
                section_nums.append(int(d[1][len("Section"):]))
        sections = ["BodyText/Section" + str(x) for x in sorted(section_nums)]
        
        # 전체 텍스트 추출
        full_text = ""
        for section in sections:
            bodytext = ole.openstream(section)
            section_data = bodytext.read()
            
            if is_compressed:
                import zlib
                unpacked_data = zlib.decompress(section_data, -15)
            else:
                unpacked_data = section_data
            
            # 레코드 구조 파싱하여 텍스트 추출
            section_text = ""
            i = 0
            size = len(unpacked_data)
            while i < size:
                header = struct.unpack_from("<I", unpacked_data, i)[0]
                rec_type = header & 0x3ff
                rec_len = (header >> 20) & 0xfff
                
                # rec_type 67 = 텍스트 레코드
                if rec_type == 67:
                    rec_data = unpacked_data[i + 4:i + 4 + rec_len]
                    try:
                        section_text += rec_data.decode('utf-16')
                        section_text += "\n"
                    except:
                        pass
                
                i += 4 + rec_len
            
            full_text += section_text
            full_text += "\n"
        
        ole.close()
        return full_text.strip()
        
    except Exception as e:
        raise ValueError(f"HWP 파일 처리 오류: {e}")
