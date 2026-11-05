"""Use-case Control classes. HTTP details and SQLite remain outside this layer.

Every command enters Restaurant.mutate once; its single transaction owns the
idempotency record, audit trail and domain-operation writes together.
"""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.restaurant import Restaurant


class CommandManager:
    def __init__(self,model:'Restaurant'):
        self.model=model

    def _execute(self,action,body,user,key):
        return self.model.mutate(action,body,user,key)


class BookingManager(CommandManager):
    def createReservation(self,body,user,key):
        return self._execute('reserve',body,user,key)

    def verifyBooking(self,body,user,key):
        return self._execute('lookup',body,user,key)

    def cancelBooking(self,body,user,key):
        return self._execute('cancel',body,user,key)

    def checkQuota(self,guests=1):
        return self.model.available_slots(guests)


class QueueManager(CommandManager):
    def registerQueue(self,body,user,key):
        return self._execute('queue_create',body,user,key)

    def processCallQueue(self,body,user,key):
        return self._execute('queue_call',body,user,key)

    def processSkip(self,body,user,key):
        return self._execute('queue_skip',body,user,key)

    def assignTable(self,body,user,key):
        return self._execute('queue_seat',body,user,key)

    def cancelQueue(self,body,user,key):
        return self._execute('queue_cancel',body,user,key)



class CheckInManager(CommandManager):
    def processCheckIn(self,body,user,key):
        return self._execute('checkin',body,user,key)

    def markNoShow(self,body,user,key):
        return self._execute('no_show',body,user,key)



class OrderSessionManager(CommandManager):
    def processOpenTable(self,body,user,key):
        return self._execute('open_table',body,user,key)



class FoodOrderManager(CommandManager):
    def placeOrder(self,body,user,key):
        return self._execute('place_order',body,user,key)

    def loadActiveMenu(self,token):
        return self.model.guest(token)


class MenuManager(CommandManager):
    def saveMenu(self,body,user,key):
        return self._execute('menu_save',body,user,key)



class PaymentManager(CommandManager):
    def processPayment(self,body,user,key):
        return self._execute('pay',body,user,key)

    def closeEmpty(self,body,user,key):
        return self._execute('close_empty',body,user,key)

    def getBillSummary(self,user,order_id):
        return self.model.bill(user,order_id)


class SettlementManager(CommandManager):
    def processSettlement(self,body,user,key):
        return self._execute('settle',body,user,key)



class KitchenManager(CommandManager):
    def advanceBatch(self,body,user,key):
        return self._execute('batch_status',body,user,key)



class AuthManager(CommandManager):
    def login(self,body,user,key):
        return self._execute('login',body,user,key)

    def logout(self,body,user,key):
        return self._execute('logout',body,user,key)



class AdministrationManager(CommandManager):
    def setQuota(self,body,user,key):
        return self._execute('settings',body,user,key)

    def saveTable(self,body,user,key):
        return self._execute('table_save',body,user,key)

    def saveStaff(self,body,user,key):
        return self._execute('staff_save',body,user,key)

    def createUser(self,body,user,key):
        return self._execute('user_save',body,user,key)



class DocumentManager(CommandManager):
    def setPrintStatus(self,body,user,key):
        return self._execute('print_status',body,user,key)

    def loadDocument(self,user,job_id):
        return self.model.print_job_data(user,job_id)


class ReportManager(CommandManager):
    def workspace(self,user,date=None):
        return self.model.snapshot(user,date)

    def loadReport(self,user,date=None):
        return self.model.report_data(user,date)


class CommandRouter:
    def __init__(self,model:'Restaurant'):
        self.model=model
        self.routes={}
        self.booking=BookingManager(model)
        self.routes['reserve']=self.booking.createReservation
        self.routes['lookup']=self.booking.verifyBooking
        self.routes['cancel']=self.booking.cancelBooking
        self.queue=QueueManager(model)
        self.routes['queue_create']=self.queue.registerQueue
        self.routes['queue_call']=self.queue.processCallQueue
        self.routes['queue_skip']=self.queue.processSkip
        self.routes['queue_seat']=self.queue.assignTable
        self.routes['queue_cancel']=self.queue.cancelQueue
        self.checkin=CheckInManager(model)
        self.routes['checkin']=self.checkin.processCheckIn
        self.routes['no_show']=self.checkin.markNoShow
        self.ordersession=OrderSessionManager(model)
        self.routes['open_table']=self.ordersession.processOpenTable
        self.foodorder=FoodOrderManager(model)
        self.routes['place_order']=self.foodorder.placeOrder
        self.menu=MenuManager(model)
        self.routes['menu_save']=self.menu.saveMenu
        self.payment=PaymentManager(model)
        self.routes['pay']=self.payment.processPayment
        self.routes['close_empty']=self.payment.closeEmpty
        self.settlement=SettlementManager(model)
        self.routes['settle']=self.settlement.processSettlement
        self.kitchen=KitchenManager(model)
        self.routes['batch_status']=self.kitchen.advanceBatch
        self.auth=AuthManager(model)
        self.routes['login']=self.auth.login
        self.routes['logout']=self.auth.logout
        self.administration=AdministrationManager(model)
        self.routes['settings']=self.administration.setQuota
        self.routes['table_save']=self.administration.saveTable
        self.routes['staff_save']=self.administration.saveStaff
        self.routes['user_save']=self.administration.createUser
        self.document=DocumentManager(model)
        self.routes['print_status']=self.document.setPrintStatus
        self.reports=ReportManager(model)

    def execute(self,action,body,user,key):
        handler=self.routes.get(action)
        if handler is None:return self.model.mutate(action,body,user,key)
        return handler(body,user,key)
