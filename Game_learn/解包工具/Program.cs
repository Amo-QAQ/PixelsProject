using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Microsoft.Xna.Framework.Content;

class XnbFinal3
{
    static string ContentRoot = @"F:\steam\steamapps\common\Stardew Valley\Content\Data";
    static string OutDir = @"C:\Users\admin\Desktop\Game_learn\解包数据";
    static string GameRoot = @"F:\steam\steamapps\common\Stardew Valley";
    static Type lzxType;

    static void Main(string[] args)
    {
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            var name = new AssemblyName(e.Name).Name;
            if (name == "Microsoft.Xna.Framework") return typeof(ContentManager).Assembly;
            var p = Path.Combine(GameRoot, name + ".dll");
            if (File.Exists(p)) return Assembly.LoadFrom(p);
            p = Path.Combine(GameRoot, name + ".exe");
            if (File.Exists(p)) return Assembly.LoadFrom(p);
            return null;
        };
        try { Assembly.LoadFrom(Path.Combine(GameRoot, "StardewValley.GameData.dll")); } catch (Exception ex) { Console.WriteLine("GameData load: " + ex.Message); }
        try { Assembly.LoadFrom(Path.Combine(GameRoot, "Stardew Valley.dll")); } catch (Exception ex) { Console.WriteLine("SDV load: " + ex.Message); }
        lzxType = typeof(ContentManager).Assembly.GetType("MonoGame.Framework.Utilities.LzxDecoderStream", throwOnError: true);
        var mgrType = typeof(ContentReader).Assembly.GetType("Microsoft.Xna.Framework.Content.ContentTypeReaderManager", true);
        var prepareM = mgrType.GetMethod("PrepareType", BindingFlags.NonPublic | BindingFlags.Static);

        Directory.CreateDirectory(OutDir);
        string[] files = args.Length > 0 ? args : new[]
        {
            "Objects","Crops","NPCGiftTastes","Fish","Weapons","Tools",
            "CraftingRecipes","CookingRecipes","Quests","Buildings","Machines",
            "Bundles","Shops","mail","Monsters","FruitTrees","FarmAnimals","Buffs"
        };
        foreach (var f in files)
        {
            var path = Path.Combine(ContentRoot, f + ".xnb");
            try
            {
                var body = GetBody(path);
                using var r = new BinaryReader(new MemoryStream(body));
                int readerCount = r.Read7BitEncodedInt();
                var readerNames = new string[readerCount];
                for (int i = 0; i < readerCount; i++) { if (i > 0) r.ReadInt32(); readerNames[i] = Read7Str(r); }

                var provider = new FakeServices();
                var mgr = new ContentManager(provider);
                using var ms = new MemoryStream(body);
                var ctor = typeof(ContentReader).GetConstructor(BindingFlags.NonPublic | BindingFlags.Instance, null,
                    new[] { typeof(ContentManager), typeof(Stream), typeof(string), typeof(int), typeof(Action<IDisposable>) }, null);
                var cr = (ContentReader)ctor.Invoke(new object[] { mgr, ms, f, 5, null });

                var readAsset = typeof(ContentReader).GetMethods(BindingFlags.NonPublic | BindingFlags.Instance)
                    .First(m => m.Name == "ReadAsset" && m.IsGenericMethodDefinition && m.GetParameters().Length == 0)
                    .MakeGenericMethod(typeof(object));
                var obj = readAsset.Invoke(cr, null);
                var json = JsonSerializer.Serialize(new { note = "完整解析（修正 reader 列表 + MonoGame 反射读取）", data = obj },
                    new JsonSerializerOptions { WriteIndented = true, IncludeFields = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
                File.WriteAllText(Path.Combine(OutDir, f + ".json"), json, new UTF8Encoding(false));
                Console.WriteLine($"OK  {f}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"FAIL {f}: {ex.GetType().Name}: {ex.Message}");
                var cur = ex;
                for (int d = 0; d < 4 && cur != null; d++)
                {
                    Console.WriteLine($"   [{d}] {cur.GetType().Name}: {cur.Message}");
                    foreach (var line in (cur.StackTrace ?? "").Split('\n').Take(5))
                        Console.WriteLine("       " + line.Trim());
                    cur = cur.InnerException;
                }
            }
        }
    }

    static byte[] GetBody(string path)
    {
        using var fs = File.OpenRead(path);
        using var br = new BinaryReader(fs);
        br.ReadBytes(3); br.ReadByte(); br.ReadByte();
        var flags = br.ReadByte();
        int xnbLength = br.ReadInt32();
        bool lzx = (flags & 0x80) != 0, lz4 = (flags & 0x40) != 0;
        if (!lzx && !lz4) { using var ms2 = new MemoryStream(); fs.CopyTo(ms2); return ms2.ToArray(); }
        int decompressed = br.ReadInt32();
        Stream body = fs;
        if (lzx) body = (Stream)Activator.CreateInstance(lzxType,
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic, null,
            new object[] { fs, decompressed, xnbLength - 14 }, null);
        var raw = new byte[decompressed];
        int total = 0;
        while (total < decompressed) { int n = body.Read(raw, total, decompressed - total); if (n <= 0) break; total += n; }
        return raw;
    }

    static string StripAssembly(string s)
    {
        // 只去掉 ", Version=..., Culture=..., PublicKeyToken=..."，保留程序集名
        return System.Text.RegularExpressions.Regex.Replace(s,
            @",\s*([^,\[\]]+),\s*Version=[^,\]]+(?:,\s*Culture=[^,\]]+)?(?:,\s*PublicKeyToken=[^,\]]+)?", ", $1");
    }

    static string Read7Str(BinaryReader br)
    {
        int len = 0, shift = 0;
        while (true)
        {
            byte b = br.ReadByte();
            len |= (b & 0x7F) << shift;
            if ((b & 0x80) == 0) break;
            shift += 7;
        }
        return Encoding.UTF8.GetString(br.ReadBytes(len));
    }
}

class FakeServices : IServiceProvider
{
    public object GetService(Type serviceType) => null;
}
