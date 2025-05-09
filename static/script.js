// 获取 HTML 元素
const form = document.getElementById('upload-form');
const videoFileInput = document.getElementById('video-file');
const loadingDiv = document.getElementById('loading');
const resultsDiv = document.getElementById('results');
const outputText = document.getElementById('output-text');
const submitButton = document.getElementById('submit-button');

// 监听表单提交事件
form.addEventListener('submit', async (event) => {
    event.preventDefault(); // 阻止表单默认的页面跳转行为

    const formData = new FormData(); // 创建 FormData 对象来包装文件数据
    const videoFile = videoFileInput.files[0]; // 获取用户选择的第一个文件

    // 检查是否选择了文件
    if (!videoFile) {
        outputText.textContent = '错误：请先选择一个视频文件。';
        resultsDiv.style.display = 'block'; // 确保错误信息可见
        return; // 停止执行
    }

    formData.append('videoFile', videoFile); // 将文件添加到 FormData 中，键名 'videoFile' 必须与后端 Flask 代码中 request.files['videoFile'] 的键名一致

    // 开始处理：显示加载指示器，禁用按钮，隐藏/清空旧结果
    loadingDiv.style.display = 'block';
    resultsDiv.style.display = 'none';
    outputText.textContent = ''; // 清空上次的结果
    submitButton.disabled = true; // 禁用提交按钮防止重复提交
    submitButton.textContent = '处理中...';

    try {
        // 使用 fetch API 将 FormData 发送到后端的 /process-video 端点
        const response = await fetch('/process-video', {
            method: 'POST',
            body: formData,
            // 对于 FormData，浏览器通常会自动设置正确的 Content-Type header，一般不需要手动指定
        });

        // 解析后端返回的 JSON 数据
        const data = await response.json();

        // 检查 HTTP 响应状态码
        if (!response.ok) {
            // 如果后端返回了错误状态码 (如 400, 500), 显示错误信息
            console.error('后端错误:', data.error || `HTTP 错误! 状态码: ${response.status}`);
            // 优先显示后端返回的 data.error，如果没有则显示通用错误
            outputText.textContent = `错误：${data.error || '处理视频时发生未知错误。'}`;
        } else {
            // 如果请求成功 (状态码 2xx), 显示后端返回的摘要和测验
            outputText.textContent = data.summary_and_quiz || "未能获取到内容。";
        }

    } catch (error) {
        // 捕获网络错误（如连接失败）或 fetch 本身的错误
        console.error('网络或客户端脚本错误:', error);
        outputText.textContent = `发生网络或客户端错误：${error.message}。请检查网络连接和浏览器控制台。`;
    } finally {
        // 处理结束（无论成功或失败）：隐藏加载指示器，显示结果区域，重新启用按钮
        loadingDiv.style.display = 'none';
        resultsDiv.style.display = 'block'; // 显示结果区域
        submitButton.disabled = false; // 重新启用按钮
        submitButton.textContent = '处理视频';
        videoFileInput.value = ''; // 清空文件选择框，方便下次选择
    }
});