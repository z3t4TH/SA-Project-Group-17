"""Operations use the transaction supplied by the Restaurant facade."""
class DomainOperations:
    def __init__(self,restaurant):
        self.restaurant=restaurant
