"""El resumen del syllabus vigente en `CourseResponse` (B-065)."""

from app.domains.courses.controller import _course_response
from app.domains.courses.entities import SyllabusDocument
from tests.unit.conftest import World
from tests.unit.courses.test_course_service import new_course


async def _add(world: World, course_id: int, **kwargs: object) -> None:
    fields: dict[str, object] = {
        "course_id": course_id,
        "source_type": "pdf",
        "file_name": "syllabus.pdf",
        "file_sha256": "a" * 64,
        "byte_size": 10,
        "page_count": 3,
        "extracted_char_count": 1200,
        "extracted_text": "texto",
    }
    fields.update(kwargs)
    await world.syllabus.add_document(SyllabusDocument(**fields))  # type: ignore[arg-type]


async def test_the_syllabus_fields_are_mapped(world: World) -> None:
    course_id = await new_course(world)
    await _add(world, course_id)
    response = _course_response(await world.course_service.get(world.instructor, course_id))
    assert response.syllabus is not None
    assert (response.syllabus.filename, response.syllabus.pages) == ("syllabus.pdf", 3)
    assert response.syllabus.characters == 1200


async def test_a_course_without_syllabus_has_null(world: World) -> None:
    course_id = await new_course(world)
    response = _course_response(await world.course_service.get(world.instructor, course_id))
    assert response.syllabus is None


async def test_the_most_recent_syllabus_wins(world: World) -> None:
    course_id = await new_course(world)
    await _add(world, course_id, file_name="viejo.pdf")
    await _add(world, course_id, file_name="nuevo.pdf", page_count=5)
    response = _course_response(await world.course_service.get(world.instructor, course_id))
    assert response.syllabus is not None
    assert (response.syllabus.filename, response.syllabus.pages) == ("nuevo.pdf", 5)


async def test_only_the_base_name_is_exposed(world: World) -> None:
    course_id = await new_course(world)
    await _add(world, course_id, file_name="C:\\Users\\ana\\Docs\\plan.pdf")
    other = await new_course(world, "Otro")
    await _add(world, other, file_name="/home/ana/docs/plan2.pdf")
    for cid, expected in ((course_id, "plan.pdf"), (other, "plan2.pdf")):
        response = _course_response(await world.course_service.get(world.instructor, cid))
        assert response.syllabus is not None
        assert response.syllabus.filename == expected


async def test_pasted_text_has_no_filename(world: World) -> None:
    course_id = await new_course(world)
    await _add(world, course_id, source_type="text", file_name=None, page_count=None)
    response = _course_response(await world.course_service.get(world.instructor, course_id))
    assert response.syllabus is not None
    assert response.syllabus.filename is None
    assert response.syllabus.pages is None


async def test_the_list_does_not_resolve_the_syllabus(world: World) -> None:
    course_id = await new_course(world)
    await _add(world, course_id)
    views, _ = await world.course_service.list_courses(
        world.instructor, mine=True, status=None, limit=20, offset=0
    )
    assert _course_response(views[0]).syllabus is None
