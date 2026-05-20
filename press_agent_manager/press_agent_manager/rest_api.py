import inspect
import re
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, get_args, get_origin, get_type_hints

import frappe
import orjson
from frappe.utils import orjson_dumps
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ValidationError as PydanticValidationError
from werkzeug.exceptions import HTTPException
from werkzeug.routing import Rule
from werkzeug.utils import redirect
from werkzeug.wrappers import Response


@dataclass
class RouteMeta:
	path: str
	methods: list[str]
	allow_guest: bool
	func: Callable
	payload_type: Any | None
	payload_info: tuple[bool, bool, Any | None]  # (is_pydantic, is_list, item_type)
	query_type: Any | None
	query_info: tuple[bool, bool, Any | None]  # (is_pydantic, is_list, item_type)
	include_in_docs: bool = True
	tag: str | None = None


@dataclass
class RouteDocs:
	request_example: Any | None = None
	responses: dict[int, dict[str, Any]] | None = None
	hide: bool = False
	tags: list[str] | None = None


def api_docs(
	*,
	request_example: Any | None = None,
	responses: dict[int, dict[str, Any]] | None = None,
	hide: bool = False,
	tags: list[str] | None = None,
):
	"""
	Example:

	@docs(
	        request_example={"first": "Tanmoy", "last": "Sarkar", "age": 25},
	        responses={
	                200: {"description": "User created", "example": {"id": "USR-001", "first": "Tanmoy"}},
	                400: {"description": "Invalid payload", "example": {"error": "invalid request data"}},
	        },
	)
	"""
	meta = RouteDocs(
		request_example=request_example,
		responses=responses or {},
		hide=hide,
		tags=tags or [],
	)

	def decorator(fn: Callable):
		existing: RouteDocs | None = getattr(fn, "__api_docs__", None)
		if existing is not None:
			if meta.request_example is not None:
				existing.request_example = meta.request_example
			if meta.responses:
				existing.responses = {**(existing.responses or {}), **meta.responses}
			if meta.tags:
				existing.tags = list({*(existing.tags or []), *meta.tags})
			existing.hide = existing.hide or meta.hide
			meta_to_set = existing
		else:
			meta_to_set = meta

		setattr(fn, "__api_docs__", meta_to_set)  # noqa: B010
		return fn

	return decorator


class Router:
	def __init__(
		self,
		prefix: str = "",
		name: str | None = None,
		default_headers: dict[str, str | int | bool] | None = None,
		enable_api_docs: bool = False,
		allow_api_docs_guest_access: bool = False,
		api_docs_show_authorization_options: bool = True,
		api_docs_title: str = "API Documentation",
		api_docs_version: str = "1.0.0",
		api_docs_default_ui: Literal["swagger", "redoc"] = "swagger",
		description: str | None = None,
		default_responses: dict[int, dict[str, Any]] | None = None,
		error_message_key: str = "error",
		error_message_prettier: Callable[[dict], str] | None = None,
	):
		self.prefix = f"/api/{prefix.strip('/')}"
		prefix_path = self.prefix + "/"
		if prefix_path.startswith("/api/v1/") or prefix_path.startswith("/api/v2/"):
			raise ValueError("Router prefix cannot start with /api/v1/ or /api/v2/")

		self.name = name or self.prefix
		self.default_headers: dict[str, str | int | bool] = default_headers or {}
		self.description = description
		self.enable_api_docs = enable_api_docs
		self.api_docs_show_authorization_options = api_docs_show_authorization_options
		self.api_docs_title = api_docs_title
		self.api_docs_version = api_docs_version
		self.api_docs_default_ui = api_docs_default_ui
		self.error_message_key = error_message_key
		self.error_message_prettier = error_message_prettier
		self._routes: list[RouteMeta] = []
		self._children: list[Router] = []
		self._store_route_docs = False

		if default_responses is None:
			self.default_responses = {
				200: {"description": "OK"},
				400: {"description": "Bad Request"},
				401: {"description": "Unauthorized"},
				403: {"description": "Forbidden"},
				404: {"description": "Not Found"},
				500: {"description": "Internal Server Error"},
			}
		else:
			self.default_responses = default_responses

		if self.enable_api_docs:
			self._store_route_docs = True
			self.setup_docs_endpoint(allow_api_docs_guest_access)

	@property
	def routes(self) -> list[RouteMeta]:
		return self._routes

	def _join(self, path: str) -> str:
		path = path.strip("/")
		if not path and not self.prefix:
			return ""
		if not self.prefix:
			return path
		return f"{self.prefix}/{path}" if path else self.prefix

	def _create_method_decorator(self, method: str):
		def decorator(path: str = "", allow_guest=False, include_in_docs: bool = True):
			return _request(self, self._join(path), [method], allow_guest, include_in_docs)

		return decorator

	def head(self, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator("HEAD")(path, allow_guest, include_in_docs)

	def get(self, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator("GET")(path, allow_guest, include_in_docs)

	def post(self, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator("POST")(path, allow_guest, include_in_docs)

	def put(self, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator("PUT")(path, allow_guest, include_in_docs)

	def delete(self, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator("DELETE")(path, allow_guest, include_in_docs)

	def patch(self, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator("PATCH")(path, allow_guest, include_in_docs)

	def request(self, method: str, path: str = "", allow_guest=False, include_in_docs: bool = True):
		return self._create_method_decorator(method)(path, allow_guest, include_in_docs)

	def subrouter(
		self,
		subpath: str,
		name: str | None = None,
		description: str | None = None,
		default_headers: dict[str, str | int | bool] | None = None,
	):
		r = Router(
			name=name,
			description=description,
			enable_api_docs=False,
			default_headers=default_headers or self.default_headers,
			error_message_key=self.error_message_key,
			error_message_prettier=self.error_message_prettier,
		)
		r.prefix = self._join(subpath)
		r._store_route_docs = True
		self._children.append(r)
		return r

	def get_routes(self) -> list[RouteMeta]:
		routes = self._routes

		if self._children:
			for child in self._children:
				routes.extend(child.get_routes())

		return routes

	def setup_docs_endpoint(self, allow_guest: bool = False):
		# Setup docs/openapi.json endpoint
		def _get_openapi_json():
			return self.openapi_specs

		def _api_docs_ui(ui: str):
			if ui == "swagger":
				html = f"""
					<!DOCTYPE html>
					<html>
					<head>
					  <title>{self.api_docs_title}</title>
					  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css" />
					</head>
					<body>
					<div id="swagger-ui"></div>
					<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
					<script>
					  window.onload = () => {{
						SwaggerUIBundle({{
						  url: '{self._join("docs/openapi.json")}',
						  dom_id: '#swagger-ui'
						}});
					  }};
					</script>
					</body>
					</html>
				 		"""
			else:
				html = f"""<!DOCTYPE html>
					  <html>
						<head>
						  <title>{self.api_docs_title}</title>
						  <meta charset="utf-8"/>
						  <meta name="viewport" content="width=device-width, initial-scale=1">
						  <style>
							body {{
							  margin: 0;
							  padding: 0;
							  }}
						  </style>
						</head>
						<body>
						  <redoc spec-url='{self._join("docs/openapi.json")}'></redoc>
						  <script type="module" src="https://cdn.redoc.ly/redoc/v3.0.0-rc.0/redoc.standalone.js"> </script>
						</body>
					  </html>
				"""

			return Response(html.strip(), mimetype="text/html")

		def _swagger_api_docs_ui():
			return _api_docs_ui("swagger")

		def _redoc_api_docs_ui():
			return _api_docs_ui("redoc")

		def _redirect_to_default_ui():
			if self.api_docs_default_ui == "swagger":
				return redirect(self._join("docs/swagger"))
			elif self.api_docs_default_ui == "redoc":
				return redirect(self._join("docs/redoc"))

		self.get("docs", allow_guest=allow_guest, include_in_docs=False)(_redirect_to_default_ui)
		self.get("docs/swagger", allow_guest=allow_guest, include_in_docs=False)(_swagger_api_docs_ui)
		self.get("docs/redoc", allow_guest=allow_guest, include_in_docs=False)(_redoc_api_docs_ui)
		self.get("docs/openapi.json", allow_guest=allow_guest, include_in_docs=False)(_get_openapi_json)

	@property
	def openapi_specs(self) -> dict:
		return generate_openapi_specs(self)

	@property
	def section_tags(self) -> list[dict]:
		tags = []

		if self.description:
			tags.append({"name": self.name, "description": self.description})

		for c in self._children:
			tags.extend(c.section_tags)

		return tags


def jsonify(data, status_code=200) -> Response:
	return Response(orjson_dumps(data), status=status_code, mimetype="application/json")


def _request(
	router: Router,
	path: str,
	methods: list[str],
	allow_guest: bool,
	include_in_docs: bool = True,
):
	from frappe.api import API_URL_MAP

	_validate_http_methods(methods)

	def decorator(fn):
		payload_annotation, payload_info, _, params = _resolve_payload_annotation(fn)
		has_payload = payload_annotation is not None

		query_annotation, query_info, _, _ = _resolve_query_annotation(fn)
		has_query = query_annotation is not None

		accepts_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
		accepted_kwarg_names = {
			name
			for name, p in params.items()
			if p.kind
			in (
				inspect.Parameter.POSITIONAL_OR_KEYWORD,
				inspect.Parameter.KEYWORD_ONLY,
			)
		}

		def executor(*args, **kwargs):
			try:
				if not allow_guest and (not frappe.session or frappe.session.user == "Guest"):
					raise frappe.AuthenticationError()

				if has_query and frappe.local.request.method == "GET":
					raw_query = dict(frappe.local.request.args)
					if not raw_query:
						raw_query = {}

					if query_annotation:
						converted = _validate_and_convert_payload(
							raw_query, query_annotation, query_info, fn.__name__
						)

						if converted is None:
							error_msg = f"Invalid query parameters for {fn.__name__}"
							if query_info[0]:  # is_pydantic
								error_msg += f": expected {query_annotation.__name__} model"
							else:
								error_msg += f": expected {query_annotation.__name__}"
							raise HTTPException(
								response=jsonify(
									{router.error_message_key: error_msg},
									status_code=400,
								)
							)

						kwargs["query"] = converted

				if has_payload and frappe.local.request.method != "GET":
					raw = None
					request_data = frappe.local.request.get_data(as_text=True)
					if request_data and frappe.local.request.is_json:
						try:
							raw = orjson.loads(request_data)
						except orjson.JSONDecodeError:
							raise HTTPException(
								response=jsonify(
									{router.error_message_key: "Invalid JSON payload"},
									status_code=400,
								)
							)

					if not raw:
						raw = [] if payload_annotation is list else {}

					if raw is not None and payload_annotation:
						converted = _validate_and_convert_payload(
							raw, payload_annotation, payload_info, fn.__name__
						)

						if converted is None:
							error_msg = f"Invalid payload format for {fn.__name__}"
							if payload_info[0]:  # is_pydantic
								error_msg += f": expected {payload_annotation.__name__} model"
							else:
								error_msg += f": expected {payload_annotation.__name__}"
							raise HTTPException(
								response=jsonify(
									{router.error_message_key: error_msg},
									status_code=400,
								)
							)

						kwargs["payload"] = converted

				# Only pass known kwargs unless the function accepts **kwargs
				if accepts_var_kwargs:
					call_kwargs = kwargs
				else:
					call_kwargs = {k: v for k, v in kwargs.items() if k in accepted_kwarg_names}

				result = fn(*args, **call_kwargs)
				return _handle_function_result(result, router.default_headers)

			except HTTPException:
				raise
			except (
				frappe.AuthenticationError,
				frappe.PermissionError,
				frappe.DoesNotExistError,
				frappe.ValidationError,
				PydanticValidationError,
			) as exc:
				raise HTTPException(
					response=_build_error_response(
						exc,
						fn.__name__,
						router.error_message_key,
						router.error_message_prettier,
					)
				)
			except Exception as exc:
				if frappe.conf.developer_mode:
					print(f"Unexpected error in API endpoint {fn.__name__}: {type(exc).__name__}: {exc}")
				raise HTTPException(
					response=_build_error_response(
						exc,
						fn.__name__,
						router.error_message_key,
						router.error_message_prettier,
					)
				)

		API_URL_MAP.add(Rule(path, endpoint=executor, methods=methods))

		if router._store_route_docs:
			router.routes.append(
				RouteMeta(
					path=path,
					methods=methods,
					allow_guest=allow_guest,
					func=fn,
					payload_type=payload_annotation,
					payload_info=payload_info,
					query_type=query_annotation,
					query_info=query_info,
					include_in_docs=include_in_docs,
					tag=router.name,
				)
			)
		else:
			# Cleanup api doc examples
			delattr(fn, "__api_docs__")

		return executor

	return decorator


def _validate_http_methods(methods: list[str]) -> None:
	if not methods:
		raise ValueError("HTTP methods must be specified")
	valid_methods = {"HEAD", "GET", "POST", "PUT", "DELETE", "PATCH"}
	for method in methods:
		if method not in valid_methods:
			raise ValueError(f"Invalid HTTP method: {method}")


def _resolve_payload_annotation(
	fn: Callable,
) -> tuple[Any | None, tuple[bool, bool, Any | None], inspect.Signature, Any]:
	sig = inspect.signature(fn)
	params = sig.parameters
	param = params.get("payload")
	if not param:
		return None, (False, False, None), sig, params

	try:
		hints = get_type_hints(fn)
		annotation = hints.get("payload")
	except (NameError, AttributeError, TypeError) as e:
		if frappe.conf.developer_mode:
			print(f"Could not resolve type hints for {fn.__name__}: {e}")
		annotation = fn.__annotations__.get("payload")

	if not annotation or annotation is inspect._empty:
		if frappe.conf.developer_mode:
			print(f"payload parameter without type annotation in {fn.__name__}")
		raise frappe.ValidationError("bad request")

	# Check if it's a generic type (like list[Something])
	origin = get_origin(annotation)

	if origin is list:
		args = get_args(annotation)
		if args:
			item_type = args[0]
			# Check if the item type is a Pydantic model
			if isinstance(item_type, type) and issubclass(item_type, PydanticBaseModel):
				return list, (True, True, item_type), sig, params

		# Plain list without type annotation or non-Pydantic type
		return list, (False, True, None), sig, params

	# Reject other generic types and unions
	if isinstance(annotation, types.UnionType) or (origin is not None and origin is not list):
		if frappe.conf.developer_mode:
			print(f"unions/generics not allowed; got {annotation!r} in {fn.__name__}")
		raise frappe.ValidationError("bad request")

	is_pydantic = isinstance(annotation, type) and issubclass(annotation, PydanticBaseModel)

	if annotation not in (list, dict) and not is_pydantic:
		if frappe.conf.developer_mode:
			print(f"invalid payload type {annotation!r} in {fn.__name__}")
		raise frappe.ValidationError("bad request")

	return annotation, (is_pydantic, False, None), sig, params


def _resolve_query_annotation(
	fn: Callable,
) -> tuple[Any | None, tuple[bool, bool, Any | None], inspect.Signature, Any]:
	sig = inspect.signature(fn)
	params = sig.parameters
	param = params.get("query")
	if not param:
		return None, (False, False, None), sig, params

	try:
		hints = get_type_hints(fn)
		annotation = hints.get("query")
	except (NameError, AttributeError, TypeError) as e:
		if frappe.conf.developer_mode:
			print(f"Could not resolve type hints for {fn.__name__}: {e}")
		annotation = fn.__annotations__.get("query")

	if not annotation or annotation is inspect._empty:
		if frappe.conf.developer_mode:
			print(f"query parameter without type annotation in {fn.__name__}")
		raise frappe.ValidationError("bad request")

	# Check if it's a generic type (like list[Something])
	origin = get_origin(annotation)

	if origin is list:
		args = get_args(annotation)
		if args:
			item_type = args[0]
			if isinstance(item_type, type) and issubclass(item_type, PydanticBaseModel):
				return list, (True, True, item_type), sig, params

		return list, (False, True, None), sig, params

	# Reject other generic types and unions
	if isinstance(annotation, types.UnionType) or (origin is not None and origin is not list):
		if frappe.conf.developer_mode:
			print(f"unions/generics not allowed; got {annotation!r} in {fn.__name__}")
		raise frappe.ValidationError("bad request")

	is_pydantic = isinstance(annotation, type) and issubclass(annotation, PydanticBaseModel)

	if annotation not in (list, dict) and not is_pydantic:
		if frappe.conf.developer_mode:
			print(f"invalid query type {annotation!r} in {fn.__name__}")
		raise frappe.ValidationError("bad request")

	return annotation, (is_pydantic, False, None), sig, params


def _validate_and_convert_payload(
	raw: Any, annotation: Any, payload_info: tuple[bool, bool, Any | None], fn_name: str
) -> Any:
	is_pydantic, is_list, item_type = payload_info

	# Handle list[PydanticModel]
	if is_list and is_pydantic and item_type:
		if not isinstance(raw, list):
			if frappe.conf.developer_mode:
				print(f"invalid payload in {fn_name}: expected list, got {type(raw).__name__}")
			return None

		try:
			return [item_type(**item) if isinstance(item, dict) else item for item in raw]
		except (TypeError, PydanticValidationError) as e:
			if frappe.conf.developer_mode:
				print(f"invalid payload in {fn_name}: failed to parse list items: {e}")
			return None

	# Handle single Pydantic model
	if is_pydantic:
		if not isinstance(raw, dict):
			if frappe.conf.developer_mode:
				print(f"invalid payload in {fn_name}: expected object, got {type(raw).__name__}")
			return None
		return annotation(**raw)

	# Handle plain list or dict
	if not isinstance(raw, annotation):
		if frappe.conf.developer_mode:
			print(f"invalid payload in {fn_name}: expected {annotation.__name__}, got {type(raw).__name__}")
		return None

	return raw


def _handle_function_result(result: Any, headers: dict | None) -> Response:
	status = None
	if isinstance(result, tuple) and len(result) == 2:
		result, status = result

	if isinstance(result, Response):
		if status:
			result.status_code = status
	elif isinstance(result, dict | list):
		return jsonify(result, status_code=status or 200)
	elif isinstance(result, PydanticBaseModel):
		return jsonify(result.model_dump(mode="json"), status_code=status or 200)
	else:
		result = Response(str(result), status=status or 200, mimetype="text/plain")

	# Append headers
	if headers:
		for key, value in headers.items():
			result.headers[key] = value

	return result


def _build_error_response(
	exc: Exception,
	fn_name: str,
	error_message_key: str = "error",
	error_message_prettier: Callable[[dict], str] | None = None,
) -> Response:
	error_map = {
		(frappe.AuthenticationError, frappe.SessionExpired): (401, "login required"),
		(frappe.PermissionError,): (403, "unauthorized access"),
		(frappe.DoesNotExistError,): (404, str(exc)),
		(frappe.ValidationError,): (417, str(exc)),
	}

	msg = None
	code = None
	validation_errors = None

	for exc_types, (status_code, message) in error_map.items():
		if isinstance(exc, exc_types):
			code = status_code
			msg = message
			break

	if isinstance(exc, PydanticValidationError):
		msg = "invalid request data"
		validation_errors = [
			{
				"field": ".".join(str(x) for x in err["loc"]),
				"message": err["msg"],
			}
			for err in exc.errors()
		]
		code = 400

	if msg is None:
		msg = str(exc) if exc else "something went wrong"
		code = 500
		if frappe.conf.developer_mode:
			print(f"Unhandled exception in {fn_name}: {type(exc).__name__}: {exc}")

	response: dict = {error_message_key: msg}
	if validation_errors:
		response["validation_errors"] = validation_errors

	if error_message_prettier:
		response[error_message_key] = error_message_prettier(response)

	return jsonify(response, status_code=code or 500)


def _get_pydantic_schema(model: type, ref_template: str) -> dict:
	if hasattr(model, "model_json_schema"):
		return model.model_json_schema(ref_template=ref_template)
	elif hasattr(model, "schema"):
		return model.schema(ref_template=ref_template)
	else:
		return {"type": "object"}


def _add_pydantic_schema(model: type, components_schemas: dict) -> None:
	name = model.__name__
	if name in components_schemas:
		return

	schema = _get_pydantic_schema(model, "#/components/schemas/{model}")

	defs = schema.pop("$defs", None) or schema.pop("definitions", None)
	if isinstance(defs, dict):
		for def_name, def_schema in defs.items():
			if def_name not in components_schemas:
				components_schemas[def_name] = def_schema

	components_schemas[name] = schema


PATH_PARAM_RE = re.compile(r"<(?:(\w+):)?(\w+)>")
TYPE_MAP = {
	"string": "string",
	"int": "integer",
	"float": "number",
	"path": "string",
}
DEFAULT_TYPE = "string"


def _schema_for_payload(
	payload_type: Any,
	payload_info: tuple[bool, bool, Any | None],
	components_schemas: dict,
) -> dict | None:
	if not payload_type:
		return None

	is_pydantic, is_list, item_type = payload_info

	# Handle list[PydanticModel]
	if is_list and is_pydantic and item_type:
		_add_pydantic_schema(item_type, components_schemas)
		return {
			"type": "array",
			"items": {"$ref": f"#/components/schemas/{item_type.__name__}"},
		}

	# Handle single Pydantic model
	if is_pydantic:
		_add_pydantic_schema(payload_type, components_schemas)
		return {"$ref": f"#/components/schemas/{payload_type.__name__}"}

	# Handle dict
	if payload_type is dict:
		return {"type": "object", "additionalProperties": True}

	# Handle plain list
	if payload_type is list:
		return {"type": "array", "items": {}}

	return {"type": "object"}


def _convert_werkzeug_path_to_openapi(path: str) -> tuple[str, list]:
	params = []

	def repl(match: re.Match):
		conv, name = match.group(1), match.group(2)
		conv = conv or "string"
		schema_type = TYPE_MAP.get(conv, DEFAULT_TYPE)
		params.append(
			{
				"name": name,
				"in": "path",
				"required": True,
				"schema": {"type": schema_type},
			}
		)
		return f"{{{name}}}"

	openapi_path = PATH_PARAM_RE.sub(repl, path)
	return openapi_path, params


class _PydanticFieldInfo:
	def __init__(self, field):
		self.field = field

	def is_required(self) -> bool:
		if hasattr(self.field, "is_required"):
			return self.field.is_required()
		else:
			return self.field.required

	def get_annotation(self):
		if hasattr(self.field, "annotation"):
			return self.field.annotation
		else:
			return self.field.outer_type_


def _get_pydantic_fields(model: type) -> list:
	if hasattr(model, "model_fields"):
		return model.model_fields.items()
	elif hasattr(model, "__fields__"):
		return model.__fields__.items()
	else:
		return []


def _query_params_from_schema(payload_type: Any, is_pydantic: bool) -> list:
	if not is_pydantic:
		return []

	params = []
	for name, field in _get_pydantic_fields(payload_type):
		field_info = _PydanticFieldInfo(field)
		ann = field_info.get_annotation()

		t = "string"
		if ann in (int, float):
			t = "number"
		if ann is bool:
			t = "boolean"

		params.append(
			{
				"name": name,
				"in": "query",
				"required": field_info.is_required(),
				"schema": {"type": t},
			}
		)

	return params


def _extract_docstring_parts(func) -> tuple[str | None, str | None]:
	docstring = (func.__doc__ or "").strip()
	if not docstring:
		return None, None

	lines = docstring.strip().splitlines()
	first_line = lines[0] if lines else None
	rest_lines = "\n".join(lines[1:]).strip() if len(lines) > 1 else None

	return first_line, rest_lines


def _build_operation_tags(route_meta: RouteMeta, docs_meta: RouteDocs | None) -> list[str]:
	tags: list[str] = []
	if route_meta.tag:
		tags.append(route_meta.tag)
	if docs_meta and docs_meta.tags:
		tags.extend(t for t in docs_meta.tags if t not in tags)
	return tags


def _build_operation_responses(
	docs_meta: RouteDocs | None, default_responses: dict[int, dict[str, str]]
) -> dict[str, Any]:
	op_responses: dict[str, Any] = {}
	custom = docs_meta.responses if docs_meta and docs_meta.responses else {}

	for status, base in default_responses.items():
		desc = custom.get(status, {}).get("description", base["description"])
		example = custom.get(status, {}).get("example")
		resp_obj: dict[str, Any] = {"description": desc}  # pyright: ignore[reportRedeclaration]
		if example is not None:
			resp_obj["content"] = {"application/json": {"example": example}}
		op_responses[str(status)] = resp_obj

	for status, meta in custom.items():
		if str(status) in op_responses:
			continue
		resp_obj: dict[str, Any] = {"description": meta.get("description", "")}
		if "example" in meta:
			resp_obj["content"] = {"application/json": {"example": meta["example"]}}
		op_responses[str(status)] = resp_obj

	return op_responses


def _build_operation(
	route_meta: RouteMeta,
	method: str,
	path_params: list,
	components_schemas: dict,
	docs_meta: RouteDocs | None,
	default_responses: dict[int, dict[str, str]],
) -> dict[str, Any]:
	op: dict[str, Any] = {"operationId": route_meta.func.__name__}

	docstring_summary, docstring_desc = _extract_docstring_parts(route_meta.func)
	op["summary"] = docstring_summary
	op["description"] = docstring_desc

	tags = _build_operation_tags(route_meta, docs_meta)
	if tags:
		op["tags"] = tags

	if path_params:
		op["parameters"] = list(path_params)

	if route_meta.query_type and method == "get":
		is_pydantic, is_list, _ = route_meta.query_info
		qp = _query_params_from_schema(route_meta.query_type, is_pydantic and not is_list)
		if qp:
			op.setdefault("parameters", []).extend(qp)

	schema = _schema_for_payload(route_meta.payload_type, route_meta.payload_info, components_schemas)

	if schema:
		content_schema: dict[str, Any] = {"schema": schema}
		if docs_meta and docs_meta.request_example is not None:
			content_schema["example"] = docs_meta.request_example

		op["requestBody"] = {
			"required": True,
			"content": {"application/json": content_schema},
		}

	op["responses"] = _build_operation_responses(docs_meta, default_responses)

	return op


def generate_openapi_specs(router: Router) -> dict:
	paths: dict[str, dict] = {}
	components = {"schemas": {}}

	for r in router.get_routes():
		docs_meta: RouteDocs | None = getattr(r.func, "__api_docs__", None)
		if not r.include_in_docs or (docs_meta and docs_meta.hide):
			continue

		openapi_path, path_params = _convert_werkzeug_path_to_openapi(r.path)

		if openapi_path not in paths:
			paths[openapi_path] = {}

		for m in r.methods:
			method = m.lower()
			op = _build_operation(
				r,
				method,
				path_params,
				components["schemas"],
				docs_meta,
				router.default_responses,
			)
			paths[openapi_path][method] = op

	if router.api_docs_show_authorization_options:
		components["securitySchemes"] = {
			"Token Based Authentication": {
				"type": "apiKey",
				"in": "header",
				"name": "Authorization",
				"description": "Use: token api_key:api_secret. [Learn more](https://docs.frappe.io/framework/user/en/api/rest#1-token-based-authentication)",
			},
			"Access Token Authentication": {
				"type": "http",
				"scheme": "bearer",
				"bearerFormat": "token",
				"description": "Use: Bearer <access_token>. [Learn more](https://docs.frappe.io/framework/user/en/api/rest#3-access-token)",
			},
		}

	spec = {
		"openapi": "3.0.0",
		"info": {"title": router.api_docs_title, "version": router.api_docs_version},
		"paths": paths,
		"components": components,
		"tags": router.section_tags,
		"security": [
			{"Token Based Authentication": []},
			{"Access Token Authentication": []},
		]
		if router.api_docs_show_authorization_options
		else [],
	}
	return spec
