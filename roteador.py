import concurrent.futures
import socket
import sys
from time import sleep, time


class Roteador:
    def __init__(self, rot_ip):
        # self.tabela = {
        #     "192.168.100.11": {"Métrica": 1, "Saída": "192.168.100.11"}
        # }
        self.tabela = self.load_to_table()
        self.ip_roteador = rot_ip
        self.vizinhos_recebidos = {}
        self.ultima_atualizacao = {}

    def load_to_table(self) -> dict[str, dict[str, str | int]]:
        with open("roteadores.txt", "r") as f:
            return {
                line.strip(): {"Métrica": 1, "Saída": line.strip()}
                for line in f.readlines()
            }

    def tabela_2_message(self) -> str:
        return "".join([f"#{ip}-{val['Métrica']}" for ip, val in self.tabela.items()])

    def anuncia_message(self, ip):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        message = ("*" + self.ip_roteador).encode("utf-8")
        sock.sendto(message, (ip, 9000))

    def me_anuncia(self):
        ips = [ip for ip in self.tabela.keys()]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(self.anuncia_message, ips)

    def send_message(self, ip):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"Sending the message: {self.tabela_2_message()} to {ip}")
        message = self.tabela_2_message().encode("utf-8")
        sock.sendto(message, (ip, 9000))

    def decode_message(self, message: str, sender: str):
        print(f"Message recieved {message}")
        print(f"Sender recieved {sender}")
        if message.startswith("*"):
            novo_ip = message[1:]
            if novo_ip not in self.tabela:
                self.tabela[novo_ip] = {"Métrica": 1, "Saída": sender}
                self.atualiza_tabela()
        elif message.startswith("#"):
            list_of_messages = message.split("#")[1:]
            for msg in list_of_messages:
                ip, metric = msg.split("-")
                metric = int(metric)
                ip_from_tab = self.tabela.get(ip)
                if ip_from_tab is None:
                    self.tabela[ip] = {"Métrica": metric + 1, "Saída": sender}
                    self.atualiza_tabela()
                elif metric + 1 < int(ip_from_tab["Métrica"]):
                    self.tabela[ip] = {"Métrica": metric + 1, "Saída": sender}
                    self.atualiza_tabela()
            self.vizinhos_recebidos[sender] = time()

    def roteia(self):
        while True:
            ips = [ip for ip in self.tabela.keys()]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                executor.map(self.send_message, ips)
            self.verifica_vizinhos()
            sleep(15)

    def get_messages(self):
        print("Checking messages")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.ip_roteador, 9000))
        while True:
            data, addr = sock.recvfrom(1024)
            self.decode_message(data.decode("utf-8"), addr[0])

    def verifica_vizinhos(self):
        tempo_atual = time()
        remover = [
            ip
            for ip, last_time in self.vizinhos_recebidos.items()
            if tempo_atual - last_time > 35
        ]
        for ip in remover:
            self.tabela = {
                dest: val for dest, val in self.tabela.items() if val["Saída"] != ip
            }
            self.atualiza_tabela()
            del self.vizinhos_recebidos[ip]

    def atualiza_tabela(self):
        print(f"Tabela de roteamento atualizada para o roteador {self.ip_roteador}:")
        for ip, info in self.tabela.items():
            print(f"IP: {ip}, Métrica: {info['Métrica']}, Saída: {info['Saída']}")

    def enviar_mensagem_texto(self, ip_destino: str, mensagem: str):
        if ip_destino in self.tabela:
            prox_ip = self.tabela[ip_destino]["Saída"]
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            texto = f"!{self.ip_roteador};{ip_destino};{mensagem}".encode("utf-8")
            sock.sendto(texto, (prox_ip, 9000))
        else:
            print(f"Rota para {ip_destino} não encontrada.")

    def handle_text_message(self, message: str):
        partes = message.split(";")
        ip_origem = partes[0][1:]
        ip_destino = partes[1]
        texto = partes[2]
        if ip_destino == self.ip_roteador:
            print(f"Mensagem recebida de {ip_origem}: {texto}")
        else:
            print(
                f"Repassando mensagem de {ip_origem} para {ip_destino} através de {self.tabela[ip_destino]['Saída']}"
            )
            self.enviar_mensagem_texto(ip_destino, texto)


if __name__ == "__main__":
    roteador = Roteador(rot_ip=sys.argv[1])
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(roteador.get_messages)
        executor.submit(roteador.roteia)
        