import os
import time # 导入 time 模块用于等待
import google.generativeai as genai
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename # 用于安全地处理文件名
from dotenv import load_dotenv # 用于加载 .env 文件中的环境变量

# --- 加载环境变量 ---
load_dotenv()

# --- 配置 ---
UPLOAD_FOLDER = 'uploads' # 上传文件存储目录 (需手动创建)
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'} # 允许的视频文件扩展名，可根据需要调整
GEMINI_MODEL_NAME = "gemini-1.5-flash" # 确保选用支持视频输入的模型 (例如 gemini-1.5-flash 或 gemini-1.5-pro)
API_KEY = os.getenv("GOOGLE_API_KEY") # 从环境变量获取 API Key

# 检查 API Key 是否已设置
if not API_KEY:
    raise ValueError("未找到 GOOGLE_API_KEY。请在项目根目录创建 .env 文件并设置该变量。")

# --- Flask 应用设置 ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024  # 示例：设置最大上传文件大小为 1GB (根据需要调整)

# 确保上传文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
        print(f"上传文件夹 '{UPLOAD_FOLDER}' 已创建。")
    except OSError as e:
        print(f"创建上传文件夹 '{UPLOAD_FOLDER}' 失败: {e}")
        # 根据情况可能需要退出或采取其他措施
        raise

# --- Google AI 客户端设置 ---
try:
    genai.configure(api_key=API_KEY)
    print(f"Google AI SDK 已使用 API Key 配置成功。选用模型: {GEMINI_MODEL_NAME}")
    # 初始化模型
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    print(f"配置 Google AI SDK 时出错: {e}")
    # 可以考虑添加更详细的错误处理逻辑
    raise # 暂时重新引发异常

# --- 辅助函数：检查文件扩展名 ---
def allowed_file(filename):
    """检查文件名是否包含'.'且扩展名在允许列表中"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 路由 ---
@app.route('/')
def index():
    """提供主 HTML 页面"""
    return render_template('index.html')

@app.route('/process-video', methods=['POST'])
def process_video():
    """处理视频上传、调用 Google AI API 并返回结果"""
    if 'videoFile' not in request.files:
        print("请求中缺少 'videoFile' 部分")
        return jsonify({"error": "请求中缺少视频文件部分"}), 400

    file = request.files['videoFile']

    if file.filename == '':
        print("未选择文件")
        return jsonify({"error": "未选择任何文件"}), 400

    if file and allowed_file(file.filename):
        # 使用 secure_filename 防止恶意文件名
        filename = secure_filename(file.filename)
        # 临时保存文件到本地服务器，因为 Google SDK 的 upload_file 需要文件路径
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        google_ai_file_resource = None # 用于存储上传后的文件资源对象，方便后续删除
        try:
            # 保存文件
            file.save(filepath)
            print(f"文件已临时保存到: {filepath}")

            # 1. 上传文件到 Google AI
            print("正在上传文件到 Google AI...")
            # display_name 在 Google AI Studio 中可见，方便识别
            google_ai_file_resource = genai.upload_file(path=filepath, display_name=filename)
            print(f"文件上传成功，资源名称: {google_ai_file_resource.name} (URI: {google_ai_file_resource.uri})")

            # 2. **关键步骤**: 等待 Google AI 处理文件直到其变为 ACTIVE 状态
            print("等待 Google AI 处理文件...")
            while google_ai_file_resource.state.name == "PROCESSING":
                print(f"文件状态: {google_ai_file_resource.state.name}, 等待10秒...")
                time.sleep(10) # 等待一段时间再检查
                google_ai_file_resource = genai.get_file(google_ai_file_resource.name) # 重新获取文件状态

            # 检查最终状态
            if google_ai_file_resource.state.name == "FAILED":
                print("Google AI 文件处理失败。")
                raise ValueError(f"文件 '{google_ai_file_resource.name}' 处理失败。")
            elif google_ai_file_resource.state.name != "ACTIVE":
                print(f"文件 '{google_ai_file_resource.name}' 未能激活，当前状态: {google_ai_file_resource.state.name}")
                raise ValueError(f"文件未能准备就绪，状态: {google_ai_file_resource.state.name}")

            print(f"文件 '{google_ai_file_resource.name}' 已激活，开始生成内容...")

            # 3. 使用上传的文件生成内容
            prompt = "请总结这个视频。然后，根据视频中的信息，创建一个包含3个问题的测验，并附带答案。"
            # 确保这里的模型实例是之前初始化的那个
            response = model.generate_content([google_ai_file_resource, prompt]) # 将文件资源对象和提示传递给模型

            print("内容已生成。")

            # 4. 将生成的文本作为 JSON 返回给前端
            return jsonify({"summary_and_quiz": response.text})

        except Exception as e:
            # 捕获文件保存、上传或内容生成过程中的所有异常
            print(f"处理过程中发生错误: {e}")
            # 返回统一的错误信息给前端
            return jsonify({"error": f"处理视频时发生错误: {e}"}), 500

        finally:
            # 5. 清理工作: 无论成功与否，都尝试删除临时文件和 Google AI 上的文件
            # 删除本地临时文件
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"已删除本地临时文件: {filepath}")
                except Exception as e_del_local:
                    print(f"删除本地临时文件 {filepath} 时出错: {e_del_local}")

            # (可选) 从 Google AI 删除文件以管理存储空间
            if google_ai_file_resource:
                 try:
                    print(f"正在从 Google AI 删除文件: {google_ai_file_resource.name}")
                    genai.delete_file(google_ai_file_resource.name)
                    print("已从 Google AI 删除文件。")
                 except Exception as e_del_google:
                     # 即使删除失败，也通常不是关键错误，记录日志即可
                     print(f"从 Google AI 删除文件 {google_ai_file_resource.name} 时出错: {e_del_google}")

    else:
        print(f"文件类型不允许: {file.filename}")
        return jsonify({"error": "不允许的文件类型"}), 400

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    # host='0.0.0.0' 使服务在局域网内可访问（请注意安全风险）
    # debug=True 仅用于开发环境，生产环境应设为 False
    # port=5000 指定服务监听的端口
    app.run(debug=True, host='127.0.0.1', port=5000)