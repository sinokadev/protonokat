import asyncio
import sys

class ProtoNokatClient:
    def __init__(self, host='127.0.0.1', port=8888):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.nickname = ""

    def encode_field(self, data):
        """데이터를 Size:Data 형식으로 인코딩"""
        return f"{len(str(data))}:{data}"

    def decode_field(self, field):
        """Size:Data 형식에서 실제 데이터만 추출"""
        if ':' in field:
            return field.split(':', 1)[1]
        return field

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"[*] 서버에 연결되었습니다: {self.host}:{self.port}")

        # 1. AUTH 단계 (PType|PassWord)
        password = "mypassword"
        auth_payload = f"2|{self.encode_field('AUTH')}|{self.encode_field(password)}"
        self.writer.write(auth_payload.encode())
        await self.writer.drain()

        # 2. 서버로부터 수신 대기 루프 시작
        asyncio.create_task(self.receive_messages())

        # 3. SET_USER 단계 (PType|NickName)
        self.nickname = input("[?] 사용할 닉네임을 입력하세요: ")
        set_user_payload = f"2|{self.encode_field('SET_USER')}|{self.encode_field(self.nickname)}"
        self.writer.write(set_user_payload.encode())
        await self.writer.drain()

        # 4. 메시지 송신 루프
        await self.send_loop()

    async def receive_messages(self):
        try:
            while True:
                data = await self.reader.read(2048)
                if not data:
                    print("\n[!] 서버와의 연결이 끊어졌습니다.")
                    break
                
                payload = data.decode('utf-8')
                parts = payload.split('|')
                fields = [self.decode_field(f) for f in parts[1:]]
                ptype = fields[0]

                if ptype == "AUTH_RES":
                    status = fields[1]
                    msg = fields[2] if len(fields) > 2 else ""
                    print(f"\n[시스템] 인증 결과: {status} ({msg})")

                elif ptype == "EDIT_USER":
                    self.nickname = fields[1]
                    print(f"\n[시스템] 닉네임이 변경되었습니다: {self.nickname} (사유: {fields[3]})")

                elif ptype == "RECV_MSG":
                    sender = fields[1]
                    message = fields[2]
                    print(f"\n[{sender}]: {message}")

                elif ptype == "KICK":
                    print(f"\n[!] 강제 퇴장: {fields[1]}")
                    break

        except Exception as e:
            print(f"\n[!] 수신 에러: {e}")
        finally:
            sys.exit()

    async def send_loop(self):
        print("\n--- 채팅 시작 (형식: 대상|메시지 / 예: ALL|안녕하세요) ---")
        while True:
            # 사용자 입력 (비동기 입력을 위해 run_in_executor 사용 가능하나 간단히 구현)
            user_input = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            user_input = user_input.strip()
            
            if not user_input: continue
            if '|' not in user_input:
                print("[!] 대상|메시지 형식으로 입력해주세요.")
                continue

            target, message = user_input.split('|', 1)
            
            # SEND_MSG (PType|Message|Target)
            send_payload = f"3|{self.encode_field('SEND_MSG')}|{self.encode_field(message)}|{self.encode_field(target)}"
            self.writer.write(send_payload.encode())
            await self.writer.drain()

async def main():
    client = ProtoNokatClient()
    await client.connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass