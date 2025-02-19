from datetime import datetime, timedelta

import numpy as np

from module.combat.assets import GET_ITEMS_1, GET_ITEMS_2, GET_ITEMS_3
from module.exception import MapWalkError
from module.exception import ScriptError
from module.logger import logger
from module.map.map_grids import SelectedGrids
from module.os.assets import MAP_EXIT
from module.os.map import OSMap
from module.os_handler.action_point import ActionPointLimit
from module.reward.reward import Reward
from module.ui.ui import page_os

RECORD_MISSION_ACCEPT = ('DailyRecord', 'os_mission_accept')
RECORD_MISSION_FINISH = ('DailyRecord', 'os_mission_finish')
RECORD_SUPPLY_BUY = ('DailyRecord', 'os_supply_buy')
RECORD_OBSCURE_FINISH = ('DailyRecord', 'os_obscure_finish')


class OperationSiren(Reward, OSMap):
    def os_init(self):
        """
        Call this method before doing any Operation functions.

        Pages:
            in: IN_MAP or IN_GLOBE or page_os or any page
            out: IN_MAP
        """
        logger.hr('OS init')

        # UI switching
        self.device.screenshot()
        if self.is_in_map():
            logger.info('Already in os map')
        elif self.is_in_globe():
            self.os_globe_goto_map()
            # Zone header has an animation to show.
            self.device.sleep(0.3)
            self.device.screenshot()
        else:
            if self.ui_page_appear(page_os):
                self.ui_goto_main()
            self.ui_ensure(page_os)
            # Zone header has an animation to show.
            self.device.sleep(0.3)
            self.device.screenshot()

        # Init
        _get_current_zone_success = False
        for _ in range(5):
            try:
                self.get_current_zone()
                _get_current_zone_success = True
                break
            except:
                self.handle_map_event()
            finally:
                self.device.screenshot()
        if not _get_current_zone_success:
            self.get_current_zone()

        # self.map_init()
        self.hp_reset()

        # Clear current zone
        self.run_auto_search()

        # Exit from special zones types, only SAFE and DANGEROUS are acceptable.
        if self.appear(MAP_EXIT, offset=(20, 20)):
            logger.warning('OS is in a special zone type, while SAFE and DANGEROUS are acceptable')
            self.map_exit()

    def globe_goto(self, zone, types=('SAFE', 'DANGEROUS'), refresh=False, stop_if_safe=False):
        """
        Goto another zone in OS.

        Args:
            zone (str, int, Zone): Name in CN/EN/JP, zone id, or Zone instance.
            types (tuple[str], list[str], str): Zone types, or a list of them.
                Available types: DANGEROUS, SAFE, OBSCURE, LOGGER, STRONGHOLD.
                Try the the first selection in type list, if not available, try the next one.
            refresh (bool): If already at target zone,
                set false to skip zone switching,
                set true to re-enter current zone to refresh.

        Pages:
            in: IN_MAP or IN_GLOBE
            out: IN_MAP
        """
        zone = self.name_to_zone(zone)
        logger.hr(f'Globe goto: {zone}')
        if self.zone == zone:
            if refresh:
                logger.info('Goto another zone to refresh current zone')
                self.globe_goto(self.zone_nearest_azur_port(self.zone), types=('SAFE', 'DANGEROUS'), refresh=False)
            else:
                logger.info('Already at target zone')
                return False
        # IN_MAP
        if self.is_in_map():
            self.os_map_goto_globe()
        # IN_GLOBE
        if not self.is_in_globe():
            logger.warning('Trying to move in globe, but not in os globe map')
            raise ScriptError('Trying to move in globe, but not in os globe map')
        # self.ensure_no_zone_pinned()
        self.globe_update()
        self.globe_focus_to(zone)
        if stop_if_safe:
            if self.zone_has_safe():
                logger.info('Zone is safe, stopped')
                self.ensure_no_zone_pinned()
                return False
        self.zone_type_select(types=types)
        self.globe_enter(zone)
        # IN_MAP
        if hasattr(self, 'zone'):
            del self.zone
        self.get_current_zone()
        # self.map_init()
        return True

    def port_goto2(self):
        """
        Wraps `port_goto2()`, handle walk_out_of_step

        Returns:
            bool: If success
        """
        for _ in range(3):
            try:
                super().port_goto2()
                return True
            except MapWalkError:
                pass

            logger.info('Goto another port then re-enter')
            prev = self.zone
            self.globe_goto(self.zone_nearest_azur_port(self.zone))
            self.globe_goto(prev)

    def fleet_repair(self, revert=True):
        """
        Repair fleets in nearest port.

        Args:
            revert (bool): If go back to previous zone.
        """
        logger.hr('OS fleet repair')
        prev = self.zone
        if self.zone.is_azur_port:
            logger.info('Already in azur port')
        else:
            self.globe_goto(self.zone_nearest_azur_port(self.zone))

        self.port_goto2()
        self.port_enter()
        self.port_dock_repair()
        self.port_quit()

        if revert and prev != self.zone:
            self.globe_goto(prev)

    def handle_fleet_repair(self, revert=True):
        if self.config.OS_REPAIR_THRESHOLD > 0:
            self.hp_get()
            check = [round(data, 2) <= self.config.OS_REPAIR_THRESHOLD if use
                    else False for data, use in zip(self.hp, self.hp_has_ship)]
            if any(check):
                logger.info('At least one ship is below threshold '
                           f'{str(int(self.config.OS_REPAIR_THRESHOLD * 100))}%, '
                            'retreating to nearest azur port for repairs')
                self.fleet_repair(revert=revert)
            else:
                logger.info('No ship found to be below threshold '
                           f'{str(int(self.config.OS_REPAIR_THRESHOLD * 100))}%, '
                            'continue OS exploration')
            self.hp_reset()

    def handle_reward(self):
        backup = self.config.cover(DO_OS_IN_DAILY=False)
        if super().handle_reward():
            logger.hr('OS re-init')
            self.os_init()
        backup.recover()

    def os_port_daily(self, mission=True, supply=True):
        """
        Accept all missions and buy all supplies in all ports.
        If reach the maximum number of missions, skip accept missions in next port.
        If not having enough yellow coins or purple coins, skip buying supplies in next port.

        Args:
            mission (bool): If needs to accept missions.
            supply (bool): If needs to buy supplies.

        Returns:
            bool: True if all finished.
        """
        logger.hr('OS port daily', level=1)
        if np.random.uniform() > 0.5:
            # St. Petersburg => Liverpool => Gibraltar => NY City
            ports = [3, 1, 2, 0]
        else:
            # NY City => Gibraltar => Liverpool => St. Petersburg
            ports = [0, 2, 1, 3]

        mission_success = True
        supply_success = True
        for port in ports:
            port = self.name_to_zone(port)
            logger.hr(f'OS port daily in {port}', level=2)
            self.globe_goto(port)
            self.port_goto2()
            self.port_enter()
            if mission and mission_success:
                mission_success &= self.port_mission_accept()
            if supply and supply_success:
                supply_success &= self.port_supply_buy()
            self.port_quit()
            if not ((mission and mission_success) or (supply and supply_success)):
                return False

        return True

    def os_finish_daily_mission(self):
        """
        Finish all daily mission in Operation Siren.
        Suggest to run os_port_daily to accept missions first.

        Returns:
            bool: True if all finished.
        """
        logger.hr('OS finish daily mission', level=1)
        backup = self.config.cover(OS_ACTION_POINT_BOX_USE=True)
        while 1:
            result = self.os_get_next_mission2()
            if not result:
                break

            self.get_current_zone()
            self.run_auto_search()
            self.handle_fleet_repair(revert=False)

        backup.recover()
        return True

    def os_meowfficer_farming(self, hazard_level=5, daily=False):
        """
        Args:
            hazard_level (int): 1 to 6. Recommend 3 or 5 for higher meowfficer searching point per action points ratio.
            daily (bool): If false, loop until AP lower than OS_ACTION_POINT_PRESERVE.
                If True, loop until run out of AP (not including boxes).
                If True and ENABLE_OS_ASH_ATTACK, loop until ash beacon fully collected today,
                    then loop until run out of AP (not including boxes).
        """
        logger.hr(f'OS meowfficer farming, hazard_level={hazard_level}', level=1)
        while 1:
            self.handle_reward()
            if daily:
                if self.config.ENABLE_OS_ASH_ATTACK:
                    if self._ash_fully_collected:
                        self.config.OS_ACTION_POINT_BOX_USE = False
                else:
                    self.config.OS_ACTION_POINT_BOX_USE = False

            # (1252, 1012) is the coordinate of zone 134 (the center zone) in os_globe_map.png
            zones = self.zone_select(hazard_level=hazard_level) \
                .delete(SelectedGrids([self.zone])) \
                .delete(SelectedGrids(self.zones.select(is_port=True))) \
                .sort_by_clock_degree(center=(1252, 1012), start=self.zone.location)

            self.globe_goto(zones[0])
            self.run_auto_search()
            self.handle_fleet_repair(revert=False)

    def _clear_os_world(self):
        for hazard_level in range(self.config.OS_WORLD_MIN_LEVEL, (self.config.OS_WORLD_MAX_LEVEL + 1)):
            zones = self.zone_select(hazard_level=hazard_level) \
                .delete(SelectedGrids(self.zones.select(is_port=True))) \
                .sort_by_clock_degree(center=(1252, 1012), start=self.zone.location)

            for zone in zones:
                self.handle_reward()
                if not self.globe_goto(zone, stop_if_safe=True):
                    continue
                self.run_auto_search()
                self.handle_fleet_repair(revert=False)

    def clear_os_world(self):
        """
        Returns:
            bool: If executed.
        """
        # Force to use AP boxes
        backup = self.config.cover(OS_ACTION_POINT_PRESERVE=40, OS_ACTION_POINT_BOX_USE=True)

        # Fleet repairs before starting if needed
        self.handle_fleet_repair(revert=False)

        try:
            self._clear_os_world()
        except ActionPointLimit:
            pass

        backup.recover()
        return True

    def clear_obscure(self):
        """
        Returns:
            bool: If executed

        Raises:
            ActionPointLimit:
        """
        logger.hr('OS clear obscure zone', level=1)
        result = self.os_get_next_obscure(use_logger=self.config.OS_OBSCURE_USE_LOGGER)
        if not result:
            # No obscure coordinates, delay next run to tomorrow.
            record = self.config.get_server_last_update(since=(0,)) + timedelta(days=1)
            record = datetime.strftime(record, self.config.TIME_FORMAT)
            self.config.config.set(*RECORD_OBSCURE_FINISH, record)
            self.config.save()
            return False

        self.get_current_zone()
        self.os_order_execute(recon_scan=True, submarine_call=self.config.OS_OBSCURE_SUBMARINE_CALL)

        # Delay next run 30min or 60min.
        delta = 60 if self.config.OS_OBSCURE_SUBMARINE_CALL else 30
        record = datetime.now() + timedelta(minutes=delta)
        record = datetime.strftime(record, self.config.TIME_FORMAT)
        self.config.config.set(*RECORD_OBSCURE_FINISH, record)
        self.config.save()

        self.run_auto_search()
        self.map_exit()
        self.handle_fleet_repair(revert=False)
        return True

    def os_obscure_finish(self):
        if self.config.OS_OBSCURE_FORCE_RUN:
            logger.info('OS obscure finish is under force run')

        while 1:
            try:
                result = self.clear_obscure()
            except ActionPointLimit:
                break
            if not result:
                break
            if not self.config.OS_OBSCURE_FORCE_RUN:
                break

    def _operation_siren(self, daily=False):
        """
        Raises:
            ActionPointLimit:
        """
        mission = self.config.ENABLE_OS_MISSION_ACCEPT \
                  and not self.config.record_executed_since(option=RECORD_MISSION_ACCEPT, since=(0,))
        supply = self.config.ENABLE_OS_SUPPLY_BUY \
                 and not self.config.record_executed_since(option=RECORD_SUPPLY_BUY, since=(0,))
        if mission or supply:
            # Force to clear all missions before accepting.
            # Because players can only hold 7 mission, and unable to accept the same mission twice.
            self.os_finish_daily_mission()
            if self.os_port_daily(mission=mission, supply=supply):
                if mission:
                    self.config.record_save(RECORD_MISSION_ACCEPT)
                if supply:
                    self.config.record_save(RECORD_SUPPLY_BUY)

        # Fleet repairs before starting if needed
        self.handle_fleet_repair(revert=False)

        finish = self.config.ENABLE_OS_MISSION_FINISH \
                 and not self.config.record_executed_since(option=RECORD_MISSION_FINISH, since=(0,))
        if finish:
            if self.os_finish_daily_mission():
                self.config.record_save(RECORD_MISSION_FINISH)

        if self.config.ENABLE_OS_OBSCURE_FINISH:
            if self.config.OS_OBSCURE_FORCE_RUN:
                self.os_obscure_finish()

        if self.config.ENABLE_OS_MEOWFFICER_FARMING:
            self.os_meowfficer_farming(hazard_level=self.config.OS_MEOWFFICER_FARMING_LEVEL, daily=daily)

    def operation_siren(self):
        try:
            self._operation_siren(daily=False)
        except ActionPointLimit:
            pass

    def operation_siren_daily(self):
        """
        Returns:
            bool: If executed.
        """
        # Force to use AP boxes
        backup = self.config.cover(OS_ACTION_POINT_PRESERVE=40)

        try:
            self._operation_siren(daily=True)
        except ActionPointLimit:
            pass

        backup.recover()
        return True
