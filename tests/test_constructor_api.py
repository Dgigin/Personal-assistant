# -*- coding: utf-8 -*-
"""
Интеграционные тесты для API конструктора сводных таблиц.
"""

import os
import sys
import io
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestConstructorUpload:
    """Тесты эндпоинта /api/constructor/upload."""

    def test_upload_xlsx(self, client, tmpdir):
        """Загрузка .xlsx файла."""
        from tests.conftest import create_test_excel
        filepath = create_test_excel(str(tmpdir))
        with open(filepath, 'rb') as f:
            response = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.xlsx')},
                content_type='multipart/form-data',
            )
        assert response.status_code == 200
        data = response.get_json()
        assert 'file_id' in data
        assert 'sheets' in data
        assert len(data['sheets']) >= 1
        # Проверяем, что есть лист Sheet1
        sheet_names = [s['name'] for s in data['sheets']]
        assert 'Sheet1' in sheet_names

    def test_upload_csv(self, client, tmpdir):
        """Загрузка .csv файла."""
        from tests.conftest import create_test_csv
        filepath = create_test_csv(str(tmpdir))
        with open(filepath, 'rb') as f:
            response = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.csv')},
                content_type='multipart/form-data',
            )
        assert response.status_code == 200
        data = response.get_json()
        assert 'file_id' in data
        assert 'sheets' in data
        assert len(data['sheets']) == 1
        # Для CSV виртуальный лист — имя файла без расширения (может быть с префиксом)
        assert 'test' in data['sheets'][0]['name']

    def test_upload_no_file(self, client):
        """Загрузка без файла."""
        response = client.post('/api/constructor/upload', data={})
        assert response.status_code == 400
        assert 'error' in response.get_json()

    def test_upload_invalid_extension(self, client, tmpdir):
        """Загрузка файла с недопустимым расширением."""
        filepath = os.path.join(str(tmpdir), 'test.txt')
        with open(filepath, 'w') as f:
            f.write('not an excel')
        with open(filepath, 'rb') as f:
            response = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.txt')},
                content_type='multipart/form-data',
            )
        assert response.status_code == 400


class TestConstructorDetectHeaders:
    """Тесты эндпоинта /api/constructor/detect_headers."""

    def test_detect_headers_normal(self, client, tmpdir):
        """Определение заголовков для обычного Excel."""
        from tests.conftest import create_test_excel
        filepath = create_test_excel(str(tmpdir))
        # Сначала загружаем файл
        with open(filepath, 'rb') as f:
            upload_resp = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.xlsx')},
                content_type='multipart/form-data',
            )
        file_id = upload_resp.get_json()['file_id']

        response = client.post(
            '/api/constructor/detect_headers',
            json={'file_id': file_id, 'sheet_name': 'Sheet1'},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'best_header_row' in data
        assert 'rows_preview' in data
        assert data['best_header_row'] == 0


class TestConstructorPivot:
    """Тесты эндпоинта /api/constructor/pivot."""

    def _upload_and_get_id(self, client, tmpdir):
        """Вспомогательный метод: загружает тестовый Excel и возвращает file_id."""
        from tests.conftest import create_test_excel
        filepath = create_test_excel(str(tmpdir))
        with open(filepath, 'rb') as f:
            resp = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.xlsx')},
                content_type='multipart/form-data',
            )
        return resp.get_json()['file_id']

    def test_pivot_sum(self, client, tmpdir):
        """Построение сводной с sum."""
        file_id = self._upload_and_get_id(client, tmpdir)
        response = client.post(
            '/api/constructor/pivot',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['Город'],
                'values': ['Продажи'],
                'agg_functions': ['sum'],
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'pivot_data' in data
        assert len(data['pivot_data']) == 2  # Москва и СПб

    def test_pivot_multi_agg(self, client, tmpdir):
        """Построение сводной с несколькими агрегациями."""
        file_id = self._upload_and_get_id(client, tmpdir)
        response = client.post(
            '/api/constructor/pivot',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['Город'],
                'values': ['Продажи'],
                'agg_functions': ['sum', 'count'],
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'pivot_data' in data
        # Должны быть обе агрегации
        cols = data['columns']
        sum_cols = [c for c in cols if 'Сумма' in c]
        count_cols = [c for c in cols if 'Количество' in c]
        assert len(sum_cols) >= 1
        assert len(count_cols) >= 1

    def test_pivot_with_filters(self, client, tmpdir):
        """Построение сводной с фильтром."""
        file_id = self._upload_and_get_id(client, tmpdir)
        response = client.post(
            '/api/constructor/pivot',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['Город'],
                'values': ['Продажи'],
                'agg_functions': ['sum'],
                'filters': {
                    'Город': {'type': 'equals', 'value': 'Москва'},
                },
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['pivot_data']) == 1
        assert data['pivot_data'][0]['Город'] == 'Москва'

    def test_pivot_missing_params(self, client, tmpdir):
        """Ошибка при отсутствии обязательных параметров."""
        file_id = self._upload_and_get_id(client, tmpdir)
        response = client.post(
            '/api/constructor/pivot',
            json={'file_id': file_id, 'sheet_name': 'Sheet1'},
        )
        assert response.status_code == 400


class TestConstructorScenario:
    """Тесты эндпоинтов сценариев."""

    def test_save_and_load_scenario(self, client):
        """Сохранение и загрузка сценария."""
        # Сохраняем сценарий
        save_resp = client.post(
            '/api/constructor/scenario/save',
            json={
                'name': 'test_scenario',
                'params': {
                    'columns': ['Город', 'Продажи'],
                    'filters': {},
                    'pivot_rows': ['Город'],
                    'pivot_values': ['Продажи'],
                    'agg_functions': ['sum'],
                    'output_format': 'flat',
                },
            },
        )
        assert save_resp.status_code == 200

        # Загружаем сценарий
        load_resp = client.post(
            '/api/constructor/scenario/load',
            json={'name': 'test_scenario'},
        )
        assert load_resp.status_code == 200
        data = load_resp.get_json()
        assert 'params' in data
        assert data['params']['pivot_rows'] == ['Город']

        # Удаляем сценарий
        del_resp = client.post(
            '/api/constructor/scenario/delete',
            json={'name': 'test_scenario'},
        )
        assert del_resp.status_code == 200
        assert del_resp.get_json()['success'] is True

    def test_list_scenarios(self, client):
        """Список сценариев."""
        response = client.get('/api/constructor/scenarios')
        assert response.status_code == 200
        data = response.get_json()
        assert 'scenarios' in data

    def test_save_scenario_no_name(self, client):
        """Ошибка при сохранении сценария без имени."""
        response = client.post(
            '/api/constructor/scenario/save',
            json={'name': '', 'params': {}},
        )
        assert response.status_code == 400


class TestConstructorIntegration:
    """Полный интеграционный тест: загрузка → pivot → скачивание."""

    def test_full_pipeline(self, client, tmpdir):
        """Загрузка → pivot → download."""
        from tests.conftest import create_test_excel
        filepath = create_test_excel(str(tmpdir))

        # 1. Upload
        with open(filepath, 'rb') as f:
            upload_resp = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.xlsx')},
                content_type='multipart/form-data',
            )
        assert upload_resp.status_code == 200
        file_id = upload_resp.get_json()['file_id']

        # 2. Pivot
        pivot_resp = client.post(
            '/api/constructor/pivot',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['Город'],
                'values': ['Продажи'],
                'agg_functions': ['sum'],
            },
        )
        assert pivot_resp.status_code == 200
        pivot_data = pivot_resp.get_json()

        # 3. Download (сохраняем результат как XLSX)
        download_resp = client.post(
            '/api/constructor/download',
            json={
                'pivot_data': pivot_data['pivot_data'],
                'columns': pivot_data['columns'],
                'filename': 'result.xlsx',
                'row_columns': pivot_data.get('row_columns', ['Город']),
            },
        )
        assert download_resp.status_code == 200
        dl_data = download_resp.get_json()
        assert 'download_url' in dl_data
        assert 'file_id' in dl_data

        # 4. Закрываем файл
        close_resp = client.post(
            '/api/constructor/close',
            json={'file_id': file_id},
        )
        assert close_resp.status_code == 200
        assert close_resp.get_json()['success'] is True

    def test_full_pipeline_with_dates(self, client, tmpdir):
        """Загрузка → pivot с датами → humanize."""
        from tests.conftest import create_test_excel_with_dates
        filepath = create_test_excel_with_dates(str(tmpdir))

        # Upload
        with open(filepath, 'rb') as f:
            upload_resp = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test_dates.xlsx')},
                content_type='multipart/form-data',
            )
        assert upload_resp.status_code == 200
        file_id = upload_resp.get_json()['file_id']

        # Pivot с датами
        pivot_resp = client.post(
            '/api/constructor/pivot',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['__год__Дата'],
                'values': ['Сумма'],
                'agg_functions': ['sum'],
            },
        )
        assert pivot_resp.status_code == 200
        pivot_data = pivot_resp.get_json()
        # После humanize колонка должна называться 'Год'
        columns = pivot_data.get('columns', [])
        has_год = any('Год' in c for c in columns)
        assert has_год

        # Закрываем
        client.post('/api/constructor/close', json={'file_id': file_id})


# ==================== АСИНХРОННЫЙ PIVOT ====================

class TestConstructorAsyncPivot:
    """Тесты эндпоинтов /api/constructor/pivot_async и /api/constructor/pivot_status."""

    def test_pivot_async_basic(self, client, tmpdir):
        """Запуск асинхронного pivot и получение результата."""
        from tests.conftest import create_test_excel
        filepath = create_test_excel(str(tmpdir))

        # Upload
        with open(filepath, 'rb') as f:
            upload_resp = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.xlsx')},
                content_type='multipart/form-data',
            )
        assert upload_resp.status_code == 200
        file_id = upload_resp.get_json()['file_id']

        # Загружаем лист (чтобы был SQLite-кэш)
        load_resp = client.post(
            '/api/constructor/load',
            json={'file_id': file_id, 'sheet_name': 'Sheet1'},
        )
        assert load_resp.status_code == 200

        # Запускаем асинхронный pivot
        async_resp = client.post(
            '/api/constructor/pivot_async',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['Город'],
                'values': ['Продажи'],
                'agg_functions': ['sum'],
            },
        )
        assert async_resp.status_code == 200
        async_data = async_resp.get_json()
        assert 'task_id' in async_data
        assert async_data['status'] == 'queued'
        task_id = async_data['task_id']

        # Поллинг статуса до завершения
        import time
        deadline = time.time() + 15
        result = None
        while time.time() < deadline:
            status_resp = client.post(
                '/api/constructor/pivot_status',
                json={'task_id': task_id},
            )
            assert status_resp.status_code == 200
            status_data = status_resp.get_json()

            if status_data['status'] == 'completed':
                result = status_data['result']
                break
            elif status_data['status'] == 'error':
                pytest.fail(f"Асинхронный pivot API упал: {status_data.get('error')}")
            time.sleep(0.5)

        assert result is not None
        assert 'pivot_data' in result
        assert 'columns' in result

        # Закрываем
        client.post('/api/constructor/close', json={'file_id': file_id})

    def test_pivot_async_with_filters(self, client, tmpdir):
        """Асинхронный pivot с фильтрами через API."""
        from tests.conftest import create_test_excel
        filepath = create_test_excel(str(tmpdir))

        with open(filepath, 'rb') as f:
            upload_resp = client.post(
                '/api/constructor/upload',
                data={'file': (f, 'test.xlsx')},
                content_type='multipart/form-data',
            )
        file_id = upload_resp.get_json()['file_id']

        client.post('/api/constructor/load', json={
            'file_id': file_id, 'sheet_name': 'Sheet1',
        })

        async_resp = client.post(
            '/api/constructor/pivot_async',
            json={
                'file_id': file_id,
                'sheet_name': 'Sheet1',
                'rows': ['Город'],
                'values': ['Продажи'],
                'agg_functions': ['sum'],
                'filters': {'Город': {'type': 'equals', 'value': 'Москва'}},
            },
        )
        assert async_resp.status_code == 200
        task_id = async_resp.get_json()['task_id']

        import time
        deadline = time.time() + 15
        result = None
        while time.time() < deadline:
            status_resp = client.post(
                '/api/constructor/pivot_status',
                json={'task_id': task_id},
            )
            status_data = status_resp.get_json()
            if status_data['status'] == 'completed':
                result = status_data['result']
                break
            elif status_data['status'] == 'error':
                pytest.fail(f"Pivot с фильтром упал: {status_data.get('error')}")
            time.sleep(0.5)

        assert result is not None
        pivot_data = result.get('pivot_data', [])
        assert len(pivot_data) > 0
        # Все строки должны быть по Москве
        for row in pivot_data:
            assert row.get('Город') == 'Москва'

        client.post('/api/constructor/close', json={'file_id': file_id})

    def test_pivot_status_not_found(self, client):
        """Запрос статуса несуществующей задачи."""
        resp = client.post(
            '/api/constructor/pivot_status',
            json={'task_id': 'nonexistent_task_id'},
        )
        assert resp.status_code == 404
        assert 'error' in resp.get_json()

    def test_pivot_async_no_file_id(self, client):
        """Запуск pivot без file_id."""
        resp = client.post(
            '/api/constructor/pivot_async',
            json={'rows': ['A'], 'values': ['B']},
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_pivot_status_no_task_id(self, client):
        """Запрос статуса без task_id."""
        resp = client.post('/api/constructor/pivot_status', json={})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()
