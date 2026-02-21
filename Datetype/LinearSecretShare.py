from Network.Party import *
from Datetype.GR import *
class ASSecretShare:
  

    def __init__(self, share: GaloisRingElement):
        self.share = share

    def __repr__(self):
        return f"SecretShare<{self.share}>"

    def __add__(self, other):
        if isinstance(other, ASSecretShare):
            return ASSecretShare(self.share + other.share)
        else:
            raise NotImplementedError("type error")

    def __sub__(self, other):
        if isinstance(other, ASSecretShare):
            return ASSecretShare(self.share - other.share)
        raise NotImplementedError("type error")

    def __mul__(self, scalar):
        if isinstance(scalar, int) or isinstance(scalar, GaloisRingElement):
            return ASSecretShare(self.share * scalar)
        elif isinstance(scalar, ASSecretShare):
            raise TypeError(""type error"")
        else:
            raise TypeError(f""type error": {type(scalar)}")

    def __rmul__(self, scalar):
        return self.__mul__(scalar)


class ASSProtocol:

    @staticmethod
    def share_secret(secret: GaloisRingElement, num_parties: int) -> List[GaloisRingElement]:
        """
        x = x_1 + x_2 + ... + x_n
        """
        shares = []
        current_sum = GaloisRingElement.zero()

        for _ in range(num_parties - 1):
            r = GaloisRingElement.random()
            shares.append(r)
            current_sum = current_sum + r

        last_share = secret - current_sum
        shares.append(last_share)

        return shares

    @staticmethod
    def reconstruct(ASSecretShareList) -> GaloisRingElement:
        reconstructed_secret = GaloisRingElement.zero()
        for val in ASSecretShareList:
            reconstructed_secret = reconstructed_secret + val

        return reconstructed_secret


