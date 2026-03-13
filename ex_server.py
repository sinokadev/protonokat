import asyncio

class ProtoNokatServer:
    def __init__(self):
        self.clients = {}  # {nickname: writer}
        self.unauthenticated_clients = set()

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

                payload = data.decode('utf-8').strip()
                parts = payload.split('|')
                
                # 1. PSize 확인 (간단 구현을 위해 검증 생략 가능하나 규격상 존재)
                psize = int(parts[0])
                fields = parts[1:]

                # 2. DataLen 파싱 함수 (Size:Data -> Data)
                def parse_field(field):
                    if ':' in field:
                        size, value = field.split(':', 1)
                        return value
                    return field

                decoded_fields = [parse_field(f) for f in fields]
                ptype = decoded_fields[0]

                # --- 로직 처리 ---

                # AUTH: 인증 처리
                if ptype == "AUTH":
                    # 규격: PType|PassWord
                    status = "OK" # 예시로 무조건 승인
                    msg = "Welcome to Nokat!"
                    response = f"3|12:AUTH_RES|2:{status}|{len(msg)}:{msg}"
                    writer.write(response.encode())
                    await writer.drain()
                    authenticated = True

                # SET_USER: 프로필 설정 (AUTH 이후 필수)
                elif ptype == "SET_USER":
                    if not authenticated: continue
                    if set_user_done: continue
                    
                    nick = decoded_fields[1]
                    if nick == "ALL":
                        # ALL 사용 시 KICK
                        k_msg = "Nickname 'ALL' is not allowed."
                        writer.write(f"2|4:KICK|{len(k_msg)}:{k_msg}".encode())
                        await writer.drain()
                        break
                    
                    if nick in self.clients:
                        # 중복 시 EDIT_USER로 강제 변경 통보
                        new_nick = f"{nick}_{addr[1]}"
                        current_nickname = new_nick
                        msg = f"Nickname duplicated. Changed to {new_nick}"
                        writer.write(f"4|9:EDIT_USER|{len(new_nick)}:{new_nick}|1:2|{len(msg)}:{msg}".encode())
                    else:
                        current_nickname = nick
                    
                    self.clients[current_nickname] = writer
                    set_user_done = True
                    print(f"[+] 유저 등록: {current_nickname}")

                # SEND_MSG: 메시지 중계
                elif ptype == "SEND_MSG":
                    if not set_user_done: continue
                    
                    msg_content = decoded_fields[1]
                    target = decoded_fields[2]
                    
                    # RECV_MSG 생성
                    recv_payload = f"3|8:RECV_MSG|{len(current_nickname)}:{current_nickname}|{len(msg_content)}:{msg_content}"
                    
                    if target == "ALL":
                        for nick, w in self.clients.items():
                            if nick != current_nickname:
                                w.write(recv_payload.encode())
                                await w.drain()
                    elif target in self.clients:
                        self.clients[target].write(recv_payload.encode())
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
    server = await asyncio.start_server(server_logic.handle_client, '127.0.0.1', 8888)
    print("[*] ProtoNokat 서버가 8888 포트에서 대기 중입니다...")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())