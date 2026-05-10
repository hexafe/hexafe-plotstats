use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{
    PyAny, PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList, PyNone, PyString, PyTuple,
};
use serde_json::{Map, Number, Value};

mod charts;
mod spec;
mod svg;

#[pyfunction]
fn render_histogram_png(py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    render_chart(py, mapping, "histogram", charts::render_histogram)
}

#[pyfunction]
fn render_violin_png(py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    render_chart(py, mapping, "violin", charts::render_violin)
}

#[pyfunction]
fn render_iqr_png(py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    render_chart(py, mapping, "iqr", charts::render_iqr)
}

#[pyfunction]
fn render_scatter_png(py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    render_chart(py, mapping, "scatter", charts::render_scatter)
}

#[pyfunction]
fn render_scatter_trend_png(py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    render_chart(py, mapping, "scatter", charts::render_scatter)
}

#[pymodule]
fn _hexafe_plotstats_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("ACCEPTS_JSON_SPEC", true)?;
    module.add_function(wrap_pyfunction!(render_histogram_png, module)?)?;
    module.add_function(wrap_pyfunction!(render_violin_png, module)?)?;
    module.add_function(wrap_pyfunction!(render_iqr_png, module)?)?;
    module.add_function(wrap_pyfunction!(render_scatter_png, module)?)?;
    module.add_function(wrap_pyfunction!(render_scatter_trend_png, module)?)?;
    Ok(())
}

fn render_chart(
    py: Python<'_>,
    mapping: &Bound<'_, PyAny>,
    chart: &str,
    renderer: fn(&Value) -> spec::RenderResult<svg::RenderedChart>,
) -> PyResult<Py<PyAny>> {
    let value = spec_from_python(mapping)?;
    let rendered = renderer(&value).map_err(|error| PyValueError::new_err(error.to_string()))?;

    let metadata = PyDict::new(py);
    metadata.set_item("chart", chart)?;
    metadata.set_item("renderer", "tiny-skia-svg")?;
    metadata.set_item("schema_version", spec::SCHEMA_VERSION)?;
    metadata.set_item("width", rendered.width)?;
    metadata.set_item("height", rendered.height)?;
    metadata.set_item("primitive_count", rendered.primitive_count)?;
    metadata.set_item("png_compression", svg::png_compression_label())?;
    if !rendered.svg.is_empty() {
        metadata.set_item("svg", rendered.svg)?;
    }

    let result = PyDict::new(py);
    result.set_item(
        "png_bytes",
        pyo3::types::PyBytes::new(py, &rendered.png_bytes),
    )?;
    result.set_item("backend", "rust")?;
    result.set_item("metadata", metadata)?;
    Ok(result.into())
}

fn spec_from_python(value: &Bound<'_, PyAny>) -> PyResult<Value> {
    if value.is_instance_of::<PyString>() {
        let raw = value.extract::<String>()?;
        return serde_json::from_str(&raw).map_err(|exc| {
            PyValueError::new_err(format!("failed to parse resolved spec JSON: {exc}"))
        });
    }
    if let Ok(bytes) = value.cast::<PyBytes>() {
        return serde_json::from_slice(bytes.as_bytes()).map_err(|exc| {
            PyValueError::new_err(format!("failed to parse resolved spec JSON: {exc}"))
        });
    }
    py_to_json_value(value)
}

fn py_to_json_value(value: &Bound<'_, PyAny>) -> PyResult<Value> {
    if value.is_instance_of::<PyNone>() {
        return Ok(Value::Null);
    }
    if value.is_instance_of::<PyBool>() {
        return Ok(Value::Bool(value.extract::<bool>()?));
    }
    if value.is_instance_of::<PyInt>() {
        let number = value.extract::<i64>()?;
        return Ok(Value::Number(Number::from(number)));
    }
    if value.is_instance_of::<PyFloat>() {
        let number = value.extract::<f64>()?;
        if !number.is_finite() {
            return Ok(Value::Null);
        }
        let Some(json_number) = Number::from_f64(number) else {
            return Ok(Value::Null);
        };
        return Ok(Value::Number(json_number));
    }
    if value.is_instance_of::<PyString>() {
        return Ok(Value::String(value.extract::<String>()?));
    }
    if let Ok(dict) = value.cast::<PyDict>() {
        let mut object = Map::new();
        for (key, item) in dict.iter() {
            object.insert(key.extract::<String>()?, py_to_json_value(&item)?);
        }
        return Ok(Value::Object(object));
    }
    if let Ok(list) = value.cast::<PyList>() {
        let mut items = Vec::with_capacity(list.len());
        for item in list.iter() {
            items.push(py_to_json_value(&item)?);
        }
        return Ok(Value::Array(items));
    }
    if let Ok(tuple) = value.cast::<PyTuple>() {
        let mut items = Vec::with_capacity(tuple.len());
        for item in tuple.iter() {
            items.push(py_to_json_value(&item)?);
        }
        return Ok(Value::Array(items));
    }

    Ok(Value::String(value.str()?.extract::<String>()?))
}
