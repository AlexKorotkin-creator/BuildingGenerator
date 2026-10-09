# -*- coding: utf-8 -*-
"""
make_euw.py - пересоздаёт EUW_ContourReport правильным типом ассета.

Мост в движок умеет делать только WidgetBlueprint, а пункт
"Run Editor Utility Widget" в контекстном меню появляется исключительно
у EditorUtilityWidgetBlueprint. Эта разница и мешала запустить виджет.

Запуск в Unreal (Output Log -> Cmd):
    py "<папка генератора>/Scripts/make_euw.py"

Скрипт удаляет старый ассет и создаёт пустой правильного типа.
Начинку (поля, кнопку, граф) после этого соберёт Claude через мост.
"""

import unreal

PKG_PATH = "/Game/My_Buildings"
ASSET_NAME = "EUW_ContourReport"
FULL = "%s/%s" % (PKG_PATH, ASSET_NAME)


def main():
    eal = unreal.EditorAssetLibrary

    if eal.does_asset_exist(FULL):
        print("[make_euw] удаляю старый ассет: %s" % FULL)
        if not eal.delete_asset(FULL):
            print("[make_euw] ОШИБКА: не смог удалить. Закрой вкладку ассета и повтори.")
            return

    factory = unreal.EditorUtilityWidgetBlueprintFactory()
    try:
        factory.set_editor_property("parent_class", unreal.EditorUtilityWidget)
    except Exception as e:
        print("[make_euw] parent_class не задался (%s) - оставляю по умолчанию" % e)

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(ASSET_NAME, PKG_PATH, None, factory)

    if asset is None:
        print("[make_euw] ОШИБКА: ассет не создан.")
        return

    eal.save_asset(FULL)
    print("[make_euw] создан: %s" % FULL)
    print("[make_euw] класс ассета: %s" % type(asset).__name__)
    print("[make_euw] ГОТОВО - скажи Claude, он соберёт начинку.")


main()
