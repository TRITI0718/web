from flask import Flask, render_template

app = Flask(__name__)

@app.get("/")
def home():
    # 完整的作品集四大分类数据
    portfolio_data = [
        {
            "category_id": "character",
            "category_name": "角色设计",
            "images": [
                {"src": "images/character/char1.jpeg", "title": "01", },
                {"src": "images/character/char2.jpeg", "title": "02", },
                {"src": "images/character/char3.jpeg", "title": "03", },
                {"src": "images/character/char4.jpeg", "title": "04", },
                {"src": "images/character/char5.jpeg", "title": "05", },
                {"src": "images/character/char6.jpeg", "title": "06", },
            ]
        },
        {
            "category_id": "illustration",
            "category_name": "插图",
            "images": [
                {"src": "images/illustration/ill1.jpeg", "title": "01", },
                {"src": "images/illustration/ill2.jpeg", "title": "02", },
                {"src": "images/illustration/ill3.jpeg", "title": "03", },
                {"src": "images/illustration/ill4.jpeg", "title": "04", },
            ]
        },
        {
            "category_id": "chibi",
            "category_name": "Q版立绘",
            "images": [
                {"src": "images/chibi/chibi1.jpeg", "title": "01", },
                {"src": "images/chibi/chibi2.jpeg", "title": "02", },

            ]
        },
        {
            "category_id": "print_book",
            "category_name": "印刷画集",
            "images": [
                {"src": "images/print_book/print1.jpeg", "title": "插画集", },
                {"src": "images/print_book/print2.jpeg", "title": "折页", },
            ]
        }
    ]
    return render_template("index.html", portfolio_data=portfolio_data)

if __name__ == "__main__":
    app.run(debug=True, port=5001)