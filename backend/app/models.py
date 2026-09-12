import enum


class OrderStatus(str, enum.Enum):
    pendiente = "pendiente"
    confirmado = "confirmado"
    en_camino = "en_camino"
    entregado = "entregado"
    cancelado = "cancelado"
