from module.base.timer import Timer
from module.logger import logger
from module.map.map_operation import MapOperation
from module.os.globe_zone import ZoneManager
from module.os_handler.action_point import ActionPointHandler
from module.os_handler.assets import *
from module.os_handler.enemy_searching import EnemySearchingHandler


class MapOrderHandler(MapOperation, ActionPointHandler, EnemySearchingHandler, ZoneManager):
    def is_in_map_order(self):
        return self.appear(ORDER_CHECK, offset=(20, 20))

    def order_enter(self):
        """
        Pages:
            in: is_in_map
            out: is_in_map_order
        """
        self.ui_click(ORDER_ENTER, appear_button=self.is_in_map, check_button=self.is_in_map_order,
                      skip_first_screenshot=True)

    def order_quit(self):
        """
        Pages:
            in: is_in_map_order
            out: is_in_map
        """
        self.ui_click(ORDER_CHECK, appear_button=self.is_in_map_order, check_button=self.is_in_map,
                      skip_first_screenshot=True)

    def order_execute(self, button, skip_first_screenshot=True):
        """
        Args:
            button (Button): A button in navigational order page.
            skip_first_screenshot (bool):

        Returns:
            bool: If success

        Pages:
            in: is_in_map
            out: is_in_map
        """
        logger.hr(button)
        self.order_enter()

        missing_timer = Timer(1, count=3).start()
        confirm_timer = Timer(1.2, count=4)
        assume_zone = self.name_to_zone(11)

        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            # End
            if self.is_in_map():
                if confirm_timer.reached():
                    return True
            else:
                confirm_timer.reset()

            if self.is_in_map_order():
                if not self.appear(button):
                    if missing_timer.reached():
                        logger.info(f'Map order not available: {button}')
                        self.order_quit()
                        return False
                else:
                    missing_timer.reset()

            if self.appear_then_click(button, interval=3):
                continue
            if self.handle_popup_confirm(button.name):
                continue
            if self.handle_map_cat_attack():
                continue
            if self.handle_action_point(zone=assume_zone, pinned='OBSCURE'):
                # After clicking action point cancel, Azur Lane closes map order, instead of staying there.
                # So re-enter map order, and re-executing the order.
                self.order_enter()
                confirm_timer.reset()
                missing_timer.reset()
                continue

    def os_order_execute(self, recon_scan=True, submarine_call=True):
        """
        Do navigational orders.

        Note that,
        A recon_scan needs 30min to cool down, and a submarine_call needs 60min.
        This method will force to use AP boxes.
        If an order is still in CD, it will cost extra AP.
        A recon_scan needs 10 AP at max, and a submarine_call needs 39 AP at max.

        Args:
            recon_scan (bool): If do recon scan
            submarine_call (bool): If do submarine call

        Pages:
            in: is_in_map
            out: is_in_map
        """
        backup = self.config.cover(OS_ACTION_POINT_PRESERVE=0, OS_ACTION_POINT_BOX_USE=True)

        if recon_scan:
            self.order_execute(ORDER_SCAN)
        if submarine_call:
            self.order_execute(ORDER_SUBMARINE)

        backup.recover()
