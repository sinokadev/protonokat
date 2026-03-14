import asyncio

class ProtoNokatServer:
    def __init__(self):
        self.clients = {}  # {nickname: writer}

    def encode_field(self, data):
        """데이터를 UTF-8 바이트 기준으로 'Size:Data' 형식으로 변환"""
        if data is None:
            data = ""
        data_str = str(data)
        byte_len = len(data_str.encode('utf-8'))
        return f"{byte_len}:{data_str}"

    def build_payload(self, *args):
        """가변 인자를 받아 PSize와 인코딩된 필드들을 합쳐 전체 페이로드 생성"""
        encoded_fields = [self.encode_field(arg) for arg in args]
        psize = len(encoded_fields)
        return f"{psize}|" + "|".join(encoded_fields)

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"[*] 신규 연결: {addr}")
        
        current_nickname = None
        authenticated = False
        set_user_done = False

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                # 수신 데이터 처리
                payload = data.decode('utf-8').strip()
                if not payload: continue
                
                parts = payload.split('|')
                # 규격상 첫 번째는 PSize, 그 뒤는 DataLen:Data 형태들
                fields_raw = parts[1:]

                def parse_field(field):
                    if ':' in field:
                        # 첫 번째 ':'를 기준으로 분리 (데이터 내에 ':'가 있을 수 있음)
                        _, value = field.split(':', 1)
                        return value
                    return field

                decoded_fields = [parse_field(f) for f in fields_raw]
                if not decoded_fields: continue
                
                ptype = decoded_fields[0]

                # --- 로직 처리 ---

                # 1. AUTH
                if ptype == "AUTH":
                    status = "OK"
                    msg = "Welcome to Nokat! 안녕하세요!" # 한글 포함 테스트
                    response = self.build_payload("AUTH_RES", status, msg)
                    writer.write(response.encode('utf-8'))
                    await writer.drain()
                    authenticated = True

                # 2. SET_USER
                elif ptype == "SET_USER":
                    if not authenticated or set_user_done: continue
                    
                    nick = decoded_fields[1]
                    if nick == "ALL":
                        k_msg = "Nickname 'ALL' is forbidden."
                        writer.write(self.build_payload("KICK", k_msg).encode('utf-8'))
                        await writer.drain()
                        break
                    
                    if nick in self.clients:
                        new_nick = f"{nick}_{addr[1]}"
                        msg = f"중복된 닉네임입니다. {new_nick}(으)로 변경되었습니다."
                        # EDIT_USER | NickName | Status | Message
                        response = self.build_payload("EDIT_USER", new_nick, "2", msg)
                        writer.write(response.encode('utf-8'))
                        current_nickname = new_nick
                    else:
                        current_nickname = nick
                        # 승인 통보 (Status 1: 승인)
                        response = self.build_payload("EDIT_USER", nick, "1", "Success")
                        writer.write(response.encode('utf-8'))
                    
                    self.clients[current_nickname] = writer
                    set_user_done = True
                    print(f"[+] 유저 등록: {current_nickname}")

                # 3. SEND_MSG
                elif ptype == "SEND_MSG":
                    if not set_user_done: continue
                    
                    msg_content = decoded_fields[1]
                    target = decoded_fields[2]
                    
                    # RECV_MSG | SenderNick | Message
                    recv_payload = self.build_payload("RECV_MSG", current_nickname, msg_content)
                    encoded_recv = recv_payload.encode('utf-8')
                    
                    if target == "ALL":
                        for nick, w in self.clients.items():
                            if nick != current_nickname:
                                w.write(encoded_recv)
                                await w.drain()
                    elif target in self.clients:
                        self.clients[target].write(encoded_recv)
                        await self.clients[target].drain()

        except Exception as e:
            print(f"[!] 에러 발생: {e}")
        finally:
            if current_nickname in self.clients:
                del self.clients[current_nickname]
            writer.close()
            await writer.wait_closed()
            print(f"[-] 연결 종료: {addr}")

async def main():
    server_logic = ProtoNokatServer()
    server = await asyncio.start_server(server_logic.handle_client, '0.0.0.0', 1226)
    print("[*] ProtoNokat v1.0 서버가 1226 포트에서 대기 중입니다...")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())