from fastapi import APIRouter
from app.schemas import (LotResponseModel, TaskResponseModel, TaskResultResponse, 
                         BatchTaskStatus, LotResult, TaskRefineResponse)
from celery.result import AsyncResult
from loguru import logger

router = APIRouter()

@router.get("/status_create/{task_id}", response_model=LotResponseModel)
async def get_create_task_status(task_id: str):
    """
    Проверяет статус задачи Celery и, если готово, возвращает `lot_id` и `id`.
    
    :param task_id: ID Celery-задачи.
    :return: Статус выполнения и результат (если готово).
    """
    result = AsyncResult(task_id)

    if result.state == "PENDING":
        return TaskResponseModel(status=False, message="Task is in queue", task_id=task_id)

    if result.state == "SUCCESS":
        lot_data = result.result
        return LotResponseModel(
            status=True,
            message="Lot created successfully",
            lot_id=lot_data["lot_id"],
            id=lot_data["id"]
        )

    if result.state == "FAILURE":
        return TaskResponseModel(status=False, message="Task failed", task_id=task_id)

    return TaskResponseModel(status=False, message="Unknown task state", task_id=task_id)


@router.get("/result_refine/{task_id}")
async def get_refine_task_result(task_id: str):
    task_result = AsyncResult(task_id)
    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "PENDING", "result": None}

    if task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "FAILURE", "error": str(task_result.result)}

    if task_result.state == "SUCCESS":
        return {"task_id": task_id, "status": "SUCCESS", "result": task_result.result}

    return {"task_id": task_id, "status": task_result.state, "result": None}


@router.get("/batch/status/{task_id}", response_model=BatchTaskStatus)
async def get_batch_status(task_id: str):
    """Проверка статуса выполнения пачки"""
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    
    if not task.ready():
        return BatchTaskStatus(
            task_id=task_id,
            status=task.status,
            processed=task.info.get('processed', 0),
            success=task.info.get('success', 0),
            failed=task.info.get('failed', 0)
        )
    
    return BatchTaskStatus(
        task_id=task_id,
        status=task.status,
        processed=task.result['processed'],
        success=task.result['success'],
        failed=task.result['failed'],
        results=[
            LotResult(**r) for r in task.result.get('results', [])
        ]
    )